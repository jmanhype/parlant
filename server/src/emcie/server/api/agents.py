import asyncio
from datetime import datetime
from typing import Dict, List
from fastapi import APIRouter
from pydantic import BaseModel

from emcie.server import common
from emcie.server.agents import AgentId, AgentStore
from emcie.server.models import ModelId, ModelRegistry
from emcie.server.threads import MessageId, ThreadId, ThreadStore


class AgentDTO(BaseModel):
    id: AgentId
    creation_utc: datetime


class ReactionDTO(BaseModel):
    thread_id: ThreadId
    message_id: MessageId


def create_router(
    agent_store: AgentStore,
    thread_store: ThreadStore,
    model_registry: ModelRegistry,
) -> APIRouter:
    background_tasks: Dict[str, asyncio.Task[None]] = {}

    router = APIRouter()

    class CreateAgentResponse(BaseModel):
        agent_id: AgentId

    @router.post("/")
    async def create_agent() -> CreateAgentResponse:
        agent = await agent_store.create_agent(model_id=ModelId("gpt-4-turbo"))
        return CreateAgentResponse(agent_id=agent.id)

    class ListAgentsResponse(BaseModel):
        agents: List[AgentDTO]

    @router.get("/")
    async def list_agents() -> ListAgentsResponse:
        agents = await agent_store.list_agents()

        return ListAgentsResponse(
            agents=[AgentDTO(id=a.id, creation_utc=a.creation_utc) for a in agents]
        )

    class CreateReactionRequest(BaseModel):
        thread_id: ThreadId

    class CreateReactionResponse(BaseModel):
        reaction: ReactionDTO

    @router.post("/{agent_id}/reactions")
    async def create_reaction(
        agent_id: AgentId,
        request: CreateReactionRequest,
    ) -> CreateReactionResponse:
        agent = await agent_store.read_agent(agent_id=agent_id)

        model = await model_registry.get_text_generation_model(model_id=agent.model_id)

        thread_messages = list(await thread_store.list_messages(thread_id=request.thread_id))

        message = await thread_store.create_message(
            thread_id=request.thread_id,
            role="assistant",
            content="",
            completed=False,
        )

        async def text_generation(task_id: str) -> None:
            revision = message.revision

            async for token in model.generate_text(messages=thread_messages):
                await thread_store.patch_message(
                    thread_id=request.thread_id,
                    message_id=message.id,
                    target_revision=revision,
                    content_delta=token,
                    completed=False,
                )

                revision += 1

            await thread_store.patch_message(
                thread_id=request.thread_id,
                message_id=message.id,
                target_revision=revision,
                content_delta="",
                completed=True,
            )

            background_tasks.pop(task_id)

        task_id = common.generate_id()
        background_tasks[task_id] = asyncio.create_task(text_generation(task_id))

        return CreateReactionResponse(
            reaction=ReactionDTO(
                thread_id=request.thread_id,
                message_id=message.id,
            )
        )

    return router
