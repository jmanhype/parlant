from __future__ import annotations
import asyncio
from datetime import datetime, timezone
import time
import traceback
from typing import Any, Mapping, Optional, Sequence, Type, TypeAlias
from lagom import Container

from emcie.server.core.async_utils import Timeout
from emcie.server.core.contextual_correlator import ContextualCorrelator
from emcie.server.core.agents import AgentId
from emcie.server.core.emissions import EventEmitterFactory
from emcie.server.core.end_users import EndUserId
from emcie.server.core.sessions import (
    Event,
    EventKind,
    EventSource,
    Session,
    SessionId,
    SessionListener,
    SessionStore,
)
from emcie.server.core.engines.types import Context, Engine
from emcie.server.core.logging import Logger


TaskQueue: TypeAlias = list[asyncio.Task[None]]


class MC:
    def __init__(self, container: Container) -> None:
        self._logger = container[Logger]
        self._correlator = container[ContextualCorrelator]
        self._session_store = container[SessionStore]
        self._session_listener = container[SessionListener]
        self._engine = container[Engine]
        self._event_emitter_factory = container[EventEmitterFactory]

        self._tasks_by_session = dict[SessionId, TaskQueue]()
        self._lock = asyncio.Lock()
        self._last_garbage_collection = 0.0
        self._garbage_collection_interval = 5.0

    async def __aenter__(self) -> MC:
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[object],
    ) -> bool:
        await self._collect_garbage(force=True)
        return False

    async def _collect_garbage(self, force: bool = False) -> None:
        now = time.time()

        if not force:
            if (now - self._last_garbage_collection) < self._garbage_collection_interval:
                return

        async with self._lock:
            session_ids = list(self._tasks_by_session.keys())

            for session_id in session_ids:
                task_queue = self._tasks_by_session[session_id]
                re_enqueued_tasks = []

                for task in task_queue:
                    if task.done() or force:
                        try:
                            await task
                        except Exception as exc:
                            self._logger.warning(
                                f"Awaited session task raised an exception: {traceback.format_exception(exc)}"
                            )
                    else:
                        re_enqueued_tasks.append(task)

                if re_enqueued_tasks:
                    self._tasks_by_session[session_id] = re_enqueued_tasks
                else:
                    del self._tasks_by_session[session_id]

            self._last_garbage_collection = now

    async def wait_for_update(
        self,
        session_id: SessionId,
        min_offset: int,
        kinds: Sequence[EventKind] = [],
        source: Optional[EventSource] = None,
        timeout: Timeout = Timeout.infinite(),
    ) -> bool:
        await self._collect_garbage()

        return await self._session_listener.wait_for_events(
            session_id=session_id,
            min_offset=min_offset,
            kinds=kinds,
            source=source,
            timeout=timeout,
        )

    async def create_end_user_session(
        self,
        end_user_id: EndUserId,
        agent_id: AgentId,
        title: Optional[str] = None,
        allow_greeting: bool = False,
    ) -> Session:
        await self._collect_garbage()

        session = await self._session_store.create_session(
            creation_utc=datetime.now(timezone.utc),
            end_user_id=end_user_id,
            agent_id=agent_id,
            title=title,
        )

        if allow_greeting:
            await self._dispatch_processing_task(session)

        return session

    async def post_client_event(
        self,
        session_id: SessionId,
        kind: EventKind,
        data: Mapping[str, Any],
    ) -> Event:
        await self._collect_garbage()

        event = await self._session_store.create_event(
            session_id=session_id,
            source="client",
            kind=kind,
            correlation_id=self._correlator.correlation_id,
            data=data,
        )

        session = await self._session_store.read_session(session_id)

        await self._dispatch_processing_task(session)

        return event

    async def update_consumption_offset(
        self,
        session: Session,
        new_offset: int,
    ) -> None:
        await self._session_store.update_consumption_offset(
            session.id,
            consumer_id="client",
            new_offset=new_offset,
        )

    async def _dispatch_processing_task(self, session: Session) -> None:
        async with self._lock:
            if session.id not in self._tasks_by_session:
                self._tasks_by_session[session.id] = TaskQueue()

            for task in self._tasks_by_session[session.id]:
                task.cancel()

            self._tasks_by_session[session.id].append(
                asyncio.create_task(self._process_session(session))
            )

    async def _process_session(self, session: Session) -> None:
        event_emitter = self._event_emitter_factory.create_event_emitter(session.id)

        await self._engine.process(
            Context(
                session_id=session.id,
                agent_id=session.agent_id,
            ),
            event_emitter=event_emitter,
        )
