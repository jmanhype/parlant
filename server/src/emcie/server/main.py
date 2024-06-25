from fastapi import FastAPI
from lagom import Container

from emcie.server.api import agents
from emcie.server.api import sessions
from emcie.server.core.agents import AgentStore
from emcie.server.core.sessions import SessionStore


async def create_app(container: Container) -> FastAPI:
    agent_store = container[AgentStore]
    session_store = container[SessionStore]

    app = FastAPI()

    app.include_router(
        prefix="/agents",
        router=agents.create_router(
            agent_store=agent_store,
        ),
    )

    app.mount(
        "/sessions",
        sessions.create_router(
            session_store=session_store,
        ),
    )

    return app
