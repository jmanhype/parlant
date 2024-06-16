import asyncio
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter

from emcie.server.base import EmcieBase
from emcie.server.core.agents import AgentId, AgentStore
from emcie.server.core.models import ModelId, ModelRegistry
from emcie.server.core.threads import MessageId, ThreadId, ThreadStore


class AgentDTO(EmcieBase):
    id: AgentId
    llm_id: str
    creation_utc: datetime


class ReactionDTO(EmcieBase):
    thread_id: ThreadId
    message_id: MessageId


class CreateAgentRequest(EmcieBase):
    llm_id: Optional[ModelId] = None


class CreateAgentResponse(EmcieBase):
    agent_id: AgentId


class ListAgentsResponse(EmcieBase):
    agents: List[AgentDTO]


class CreateReactionRequest(EmcieBase):
    thread_id: ThreadId


class CreateReactionResponse(EmcieBase):
    reaction: ReactionDTO


def create_router(
    agent_store: AgentStore,
    thread_store: ThreadStore,
    model_registry: ModelRegistry,
) -> APIRouter:
    router = APIRouter()

    @router.post("/")
    async def create_agent(
        request: Optional[CreateAgentRequest] = None,
    ) -> CreateAgentResponse:
        agent = await agent_store.create_agent(
            model_id=request and request.llm_id or None,
        )

        return CreateAgentResponse(agent_id=agent.id)

    @router.get("/")
    async def list_agents() -> ListAgentsResponse:
        agents = await agent_store.list_agents()

        return ListAgentsResponse(
            agents=[
                AgentDTO(id=a.id, llm_id=a.model_id, creation_utc=a.creation_utc) for a in agents
            ]
        )

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

        async def generate_message_text() -> None:
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

        _ = asyncio.create_task(generate_message_text())

        return CreateReactionResponse(
            reaction=ReactionDTO(
                thread_id=request.thread_id,
                message_id=message.id,
            )
        )

    return router
