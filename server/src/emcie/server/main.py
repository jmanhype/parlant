from fastapi import FastAPI
from lagom import Container

from emcie.server.api import agents
from emcie.server.api import sessions
from emcie.server.api import threads
from emcie.server.core.agents import AgentStore
from emcie.server.core.models import ModelId, ModelRegistry
from emcie.server.providers.openai import GPT
from emcie.server.core.sessions import SessionStore
from emcie.server.core.threads import ThreadStore


async def create_app(container: Container) -> FastAPI:
    agent_store = container[AgentStore]
    thread_store = container[ThreadStore]
    session_store = container[SessionStore]
    model_registry = container[ModelRegistry]

    models = {
        "openai/gpt-4-turbo": GPT("gpt-4-turbo-preview"),
        "openai/gpt-3.5-turbo": GPT("gpt-3.5-turbo"),
    }

    for model_id, model in models.items():
        await model_registry.add_text_generation_model(ModelId(model_id), model)

    app = FastAPI()

    app.include_router(
        prefix="/agents",
        router=agents.create_router(
            agent_store=agent_store,
            thread_store=thread_store,
            model_registry=model_registry,
        ),
    )

    app.mount(
        "/threads",
        threads.create_router(
            thread_store=thread_store,
        ),
    )

    app.mount(
        "/sessions",
        sessions.create_router(
            session_store=session_store,
        ),
    )

    return app
