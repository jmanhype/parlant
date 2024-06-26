from datetime import datetime, timezone
from typing import Any, Iterable
from lagom import Container

from emcie.server.core.agents import AgentId
from emcie.server.core.end_users import EndUserId
from emcie.server.core.sessions import Session, SessionId, SessionStore
from emcie.server.engines.common import Context, Engine, ProducedEvent


class MC:
    def __init__(self, container: Container) -> None:
        self._session_store = container[SessionStore]
        self._engine = container[Engine]

    async def create_end_user_session(
        self,
        end_user_id: EndUserId,
        agent_id: AgentId,
    ) -> Session:
        session = await self._session_store.create_session(
            end_user_id=end_user_id,
            agent_id=agent_id,
        )

        await self._update_session(session)

        return session

    async def post_client_event(
        self,
        session_id: SessionId,
        type: str,
        data: dict[str, Any],
    ) -> None:
        await self._session_store.create_event(
            session_id=session_id,
            source="client",
            type=type,
            data=data,
        )

        session = await self._session_store.read_session(session_id)

        await self._update_session(session)

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
                type=e.type,
                data=e.data,
                creation_utc=utc_now,
            )
