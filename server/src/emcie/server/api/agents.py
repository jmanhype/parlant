from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter

from emcie.server.base_models import DefaultBaseModel
from emcie.server.core.agents import AgentId, AgentStore


class AgentDTO(DefaultBaseModel):
    id: AgentId
    creation_utc: datetime


class CreateAgentRequest(DefaultBaseModel):
    id: AgentId


class CreateAgentResponse(DefaultBaseModel):
    agent_id: AgentId


class ListAgentsResponse(DefaultBaseModel):
    agents: List[AgentDTO]


def create_router(
    agent_store: AgentStore,
) -> APIRouter:
    router = APIRouter()

    @router.post("/")
    async def create_agent(
        request: Optional[CreateAgentRequest] = None,
    ) -> CreateAgentResponse:
        agent = await agent_store.create_agent()

        return CreateAgentResponse(agent_id=agent.id)

    @router.get("/")
    async def list_agents() -> ListAgentsResponse:
        agents = await agent_store.list_agents()

        return ListAgentsResponse(
            agents=[
                AgentDTO(
                    id=a.id,
                    creation_utc=a.creation_utc,
                )
                for a in agents
            ]
        )

    return router
