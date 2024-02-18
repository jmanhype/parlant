from datetime import datetime
from typing import List
from fastapi import APIRouter
from pydantic import BaseModel

from emcie.server.agents import AgentId, AgentStore
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
) -> APIRouter:
    router = APIRouter()

    class CreateAgentResponse(BaseModel):
        agent_id: AgentId

    @router.post("/")
    async def create_agent() -> CreateAgentResponse:
        agent = await agent_store.create_agent()
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
        message = await thread_store.create_message(
            thread_id=request.thread_id,
            role="assistant",
            content="Hello",
            completed=True,
        )

        return CreateReactionResponse(
            reaction=ReactionDTO(
                thread_id=request.thread_id,
                message_id=message.id,
            )
        )

    return router
