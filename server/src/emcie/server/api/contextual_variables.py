from fastapi import status
from typing import Literal, Optional

from emcie.common.tools import ToolId
from fastapi import APIRouter
from emcie.server.core.agents import AgentId
from emcie.server.core.common import DefaultBaseModel
from emcie.server.core.context_variables import (
    ContextVariableId,
    ContextVariableStore,
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

    return router
