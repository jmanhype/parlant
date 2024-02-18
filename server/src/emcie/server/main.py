from fastapi import FastAPI

from emcie.server.api import agents
from emcie.server.api import threads
from emcie.server.agents import AgentStore
from emcie.server.threads import ThreadStore


def create_app() -> FastAPI:
    agent_store = AgentStore()
    thread_store = ThreadStore()

    app = FastAPI()

    app.mount(
        "/agents",
        agents.create_router(
            agent_store=agent_store,
            thread_store=thread_store,
        ),
    )

    app.mount(
        "/threads",
        threads.create_router(
            thread_store=thread_store,
        ),
    )

    return app
