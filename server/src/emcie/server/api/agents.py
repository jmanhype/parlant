from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Response, status

from emcie.server.core.common import DefaultBaseModel
from emcie.server.core.agents import AgentId, AgentStore, AgentUpdateParams


class AgentDTO(DefaultBaseModel):
    id: AgentId
    name: str
    description: Optional[str]
    creation_utc: datetime
    max_engine_iterations: int


class CreateAgentRequest(DefaultBaseModel):
    agent_name: str
    agent_description: Optional[str] = None
    max_engine_iterations: Optional[int] = None


class CreateAgentResponse(DefaultBaseModel):
    agent_id: AgentId


class ListAgentsResponse(DefaultBaseModel):
    agents: list[AgentDTO]


class PatchAgentRequest(DefaultBaseModel):
    description: Optional[str] = None
    max_engine_iterations: Optional[int] = None


def create_router(
    agent_store: AgentStore,
) -> APIRouter:
    router = APIRouter()

    @router.post("/", status_code=status.HTTP_201_CREATED)
    async def create_agent(
        request: Optional[CreateAgentRequest] = None,
    ) -> CreateAgentResponse:
        agent = await agent_store.create_agent(
            name=request and request.agent_name or "Unnamed Agent",
            description=request and request.agent_description or None,
            max_engine_iterations=request and request.max_engine_iterations or None,
        )

        return CreateAgentResponse(agent_id=agent.id)

    @router.get("/")
    async def list_agents() -> ListAgentsResponse:
        agents = await agent_store.list_agents()

        return ListAgentsResponse(
            agents=[
                AgentDTO(
                    id=a.id,
                    name=a.name,
                    description=a.description,
                    creation_utc=a.creation_utc,
                    max_engine_iterations=a.max_engine_iterations,
                )
                for a in agents
            ]
        )

    @router.patch("/{agent_id}")
    async def patch_agent(
        agent_id: AgentId,
        request: PatchAgentRequest,
    ) -> Response:
        params: AgentUpdateParams = {}

        if request.description:
            params["description"] = request.description

        if request.max_engine_iterations:
            params["max_engine_iterations"] = request.max_engine_iterations

        await agent_store.update_agent(agent_id=agent_id, params=params)

        return Response(content=None, status_code=status.HTTP_204_NO_CONTENT)

    return router
