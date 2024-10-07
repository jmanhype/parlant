from fastapi import HTTPException, status
from typing import Literal, Optional

from emcie.common.tools import ToolId
from fastapi import APIRouter
from emcie.server.core.agents import AgentId
from emcie.server.core.common import DefaultBaseModel
from emcie.server.core.context_variables import (
    ContextVariableId,
    ContextVariableStore,
    ContextVariableValueId,
    FreshnessRules,
)
from emcie.server.core.tools import ToolService


class FreshnessRulesDTO(DefaultBaseModel):
    months: Optional[list[int]] = None
    days_of_month: Optional[list[int]] = None
    days_of_week: Optional[
        list[
            Literal[
                "Sunday",
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
            ]
        ]
    ] = None
    hours: Optional[list[int]] = None
    minutes: Optional[list[int]] = None
    seconds: Optional[list[int]] = None


class ContextVariableDTO(DefaultBaseModel):
    id: ContextVariableId
    name: str
    description: Optional[str] = None
    tool_id: ToolId
    freshness_rules: Optional[FreshnessRulesDTO] = None


class CreateContextVariableRequest(DefaultBaseModel):
    name: str
    description: Optional[str] = None
    tool_id: ToolId
    freshness_rules: Optional[FreshnessRulesDTO] = None


class CreateContextVariableResponse(DefaultBaseModel):
    variable: ContextVariableDTO


class DeleteContextVariableReponse(DefaultBaseModel):
    variable_id: ContextVariableId


class ListContextVariablesResponse(DefaultBaseModel):
    variables: list[ContextVariableDTO]


class DeleteContextVariableValueResponse(DefaultBaseModel):
    variable_value_id: ContextVariableValueId


def _freshness_ruless_dto_to_freshness_rules(dto: FreshnessRulesDTO) -> FreshnessRules:
    return FreshnessRules(
        months=dto.months,
        days_of_month=dto.days_of_month,
        days_of_week=dto.days_of_week,
        hours=dto.hours,
        minutes=dto.minutes,
        seconds=dto.seconds,
    )


def _freshness_ruless_to_dto(freshness_rules: FreshnessRules) -> FreshnessRulesDTO:
    return FreshnessRulesDTO(
        months=freshness_rules.months,
        days_of_month=freshness_rules.days_of_month,
        days_of_week=freshness_rules.days_of_week,
        hours=freshness_rules.hours,
        minutes=freshness_rules.minutes,
        seconds=freshness_rules.seconds,
    )


def create_router(
    context_variable_store: ContextVariableStore,
    tool_service: ToolService,
) -> APIRouter:
    router = APIRouter()

    @router.post("/{agent_id}/variables/", status_code=status.HTTP_201_CREATED)
    async def create_variable(
        agent_id: AgentId,
        request: CreateContextVariableRequest,
    ) -> CreateContextVariableResponse:
        _ = await tool_service.read_tool(request.tool_id)

        variable = await context_variable_store.create_variable(
            variable_set=agent_id,
            name=request.name,
            description=request.description,
            tool_id=request.tool_id,
            freshness_rules=_freshness_ruless_dto_to_freshness_rules(request.freshness_rules)
            if request.freshness_rules
            else None,
        )

        return CreateContextVariableResponse(
            variable=ContextVariableDTO(
                id=variable.id,
                name=variable.name,
                description=variable.description,
                tool_id=variable.tool_id,
                freshness_rules=_freshness_ruless_to_dto(variable.freshness_rules)
                if variable.freshness_rules
                else None,
            )
        )

    @router.delete("/{agent_id}/variables/{variable_id}/")
    async def delete_variable(
        agent_id: AgentId, variable_id: ContextVariableId
    ) -> DeleteContextVariableReponse:
        _ = await context_variable_store.delete_variable(
            variable_set=agent_id,
            id=variable_id,
        )

        return DeleteContextVariableReponse(variable_id=variable_id)

    @router.get("/{agent_id}/variables/")
    async def list_variables(
        agent_id: AgentId,
    ) -> ListContextVariablesResponse:
        variables = await context_variable_store.list_variables(variable_set=agent_id)

        return ListContextVariablesResponse(
            variables=[
                ContextVariableDTO(
                    id=variable.id,
                    name=variable.name,
                    description=variable.description,
                    tool_id=variable.tool_id,
                    freshness_rules=_freshness_ruless_to_dto(variable.freshness_rules)
                    if variable.freshness_rules
                    else None,
                )
                for variable in variables
            ]
        )

    @router.delete("/{agent_id}/variables/{variable_id}/values/{key}")
    async def delete_value(
        agent_id: AgentId,
        variable_id: ContextVariableId,
        key: str,
    ) -> DeleteContextVariableValueResponse:
        _ = await context_variable_store.read_variable(
            variable_set=agent_id,
            id=variable_id,
        )

        if deleted_variable_value_id := await context_variable_store.delete_value(
            variable_set=agent_id,
            variable_id=variable_id,
            key=key,
        ):
            return DeleteContextVariableValueResponse(variable_value_id=deleted_variable_value_id)
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return router
