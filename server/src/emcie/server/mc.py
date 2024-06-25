from lagom import Container

from emcie.server.core.agents import AgentId
from emcie.server.core.end_users import EndUserId
from emcie.server.core.sessions import Event, Session, SessionStore
from emcie.server.engines.common import Context, Engine


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
        )

        produced_events = await self._engine.process(
            Context(
                session_id=session.id,
                agent_id=agent_id,
            )
        )

        for event in produced_events:
            await self._session_store.create_event(
                session_id=session.id,
                source=event.source,
                type=event.type,
                data=event.data,
            )

        return session
