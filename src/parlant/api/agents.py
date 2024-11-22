from datetime import datetime
from typing import Optional
from fastapi import APIRouter, status

from parlant.api.common import apigen_config
from parlant.core.common import DefaultBaseModel
from parlant.core.agents import AgentId, AgentStore, AgentUpdateParams

API_GROUP = "agents"


class AgentDTO(DefaultBaseModel):
    id: AgentId
    name: str
    description: Optional[str]
    creation_utc: datetime
    max_engine_iterations: int


class AgentCreationParamsDTO(DefaultBaseModel):
    name: str
    description: Optional[str] = None
    max_engine_iterations: Optional[int] = None


class AgentCreationResult(DefaultBaseModel):
    agent: AgentDTO


class AgentListResult(DefaultBaseModel):
    agents: list[AgentDTO]


class AgentUpdateParamsDTO(DefaultBaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    max_engine_iterations: Optional[int] = None


def create_router(
    agent_store: AgentStore,
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/",
        status_code=status.HTTP_201_CREATED,
        operation_id="create_agent",
        **apigen_config(group_name=API_GROUP, method_name="create"),
    )
    async def create_agent(
        params: AgentCreationParamsDTO,
    ) -> AgentCreationResult:
        agent = await agent_store.create_agent(
            name=params and params.name or "Unnamed Agent",
            description=params and params.description or None,
            max_engine_iterations=params and params.max_engine_iterations or None,
        )

        return AgentCreationResult(
            agent=AgentDTO(
                id=agent.id,
                name=agent.name,
                description=agent.description,
                creation_utc=agent.creation_utc,
                max_engine_iterations=agent.max_engine_iterations,
            )
        )

    @router.get(
        "/",
        operation_id="list_agents",
        **apigen_config(group_name=API_GROUP, method_name="list"),
    )
    async def list_agents() -> AgentListResult:
        agents = await agent_store.list_agents()

        return AgentListResult(
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

    @router.get(
        "/{agent_id}",
        operation_id="read_agent",
        **apigen_config(group_name=API_GROUP, method_name="retrieve"),
    )
    async def read_agent(agent_id: AgentId) -> AgentDTO:
        agent = await agent_store.read_agent(agent_id=agent_id)

        return AgentDTO(
            id=agent.id,
            name=agent.name,
            description=agent.description,
            creation_utc=agent.creation_utc,
            max_engine_iterations=agent.max_engine_iterations,
        )

    @router.patch(
        "/{agent_id}",
        operation_id="update_agent",
        status_code=status.HTTP_204_NO_CONTENT,
        **apigen_config(group_name=API_GROUP, method_name="update"),
    )
    async def update_agent(
        agent_id: AgentId,
        params: AgentUpdateParamsDTO,
    ) -> None:
        def from_dto(dto: AgentUpdateParamsDTO) -> AgentUpdateParams:
            params: AgentUpdateParams = {}

            if dto.name:
                params["name"] = dto.name

            if dto.description:
                params["description"] = dto.description

            if dto.max_engine_iterations:
                params["max_engine_iterations"] = dto.max_engine_iterations

            return params

        await agent_store.update_agent(
            agent_id=agent_id,
            params=from_dto(params),
        )

    @router.delete(
        "/{agent_id}",
        operation_id="delete_agent",
        status_code=status.HTTP_204_NO_CONTENT,
        **apigen_config(group_name=API_GROUP, method_name="delete"),
    )
    async def delete_agent(
        agent_id: AgentId,
    ) -> None:
        await agent_store.delete_agent(agent_id=agent_id)

    return router
