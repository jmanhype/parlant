from fastapi import FastAPI

from emcie.server.api import agents
from emcie.server.api import threads
from emcie.server.agents import AgentStore
from emcie.server.models import ModelId, ModelRegistry
from emcie.server.providers.openai import GPT4Turbo
from emcie.server.threads import ThreadStore


async def create_app() -> FastAPI:
    agent_store = AgentStore()
    thread_store = ThreadStore()
    model_registry = ModelRegistry()

    await model_registry.add_text_generation_model(ModelId("gpt-4-turbo"), GPT4Turbo())

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

    return app
