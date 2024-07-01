from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Type
from lagom import Container

from emcie.server.async_utils import Timeout
from emcie.server.core.agents import AgentId
from emcie.server.core.end_users import EndUserId
from emcie.server.core.sessions import Event, Session, SessionId, SessionListener, SessionStore
from emcie.server.engines.common import Context, Engine, ProducedEvent


class MC:
    def __init__(self, container: Container) -> None:
        self._session_store = container[SessionStore]
        self._session_listener = container[SessionListener]
        self._engine = container[Engine]
        self._tasks = asyncio.Queue[asyncio.Task[None]]()

    async def __aenter__(self) -> MC:
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[object],
    ) -> bool:
        while not self._tasks.empty():
            task = self._tasks.get_nowait()
            await task

        return False

    async def wait_for_update(
        self,
        session_id: SessionId,
        min_offset: int,
        timeout: Timeout,
    ) -> bool:
        return await self._session_listener.wait_for_events(
            session_id=session_id,
            min_offset=min_offset,
            timeout=timeout,
        )

    async def create_end_user_session(
        self,
        end_user_id: EndUserId,
        agent_id: AgentId,
    ) -> Session:
        session = await self._session_store.create_session(
            end_user_id=end_user_id,
            agent_id=agent_id,
        )

        await self._dispatch_session_update(session)

        return session

    async def post_client_event(
        self,
        session_id: SessionId,
        kind: str,
        data: dict[str, Any],
    ) -> Event:
        event = await self._session_store.create_event(
            session_id=session_id,
            source="client",
            kind=kind,
            data=data,
        )

        session = await self._session_store.read_session(session_id)

        await self._dispatch_session_update(session)

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

    async def _dispatch_session_update(self, session: Session) -> None:
        await self._tasks.put(asyncio.create_task(self._update_session(session)))

    async def _update_session(self, session: Session) -> None:
        produced_events = await self._engine.process(
            context=Context(
                session_id=session.id,
                agent_id=session.agent_id,
            )
        )

        await self._add_events_to_session(
            session_id=session.id,
            events=produced_events,
        )

    async def _add_events_to_session(
        self,
        session_id: SessionId,
        events: Iterable[ProducedEvent],
    ) -> None:
        utc_now = datetime.now(timezone.utc)

        for e in events:
            await self._session_store.create_event(
                session_id=session_id,
                source=e.source,
                kind=e.kind,
                data=e.data,
                creation_utc=utc_now,
            )
