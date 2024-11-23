from datetime import datetime
from enum import Enum
from fastapi import HTTPException, status
from typing import Optional, cast

from fastapi import APIRouter
from parlant.api.common import ToolIdDTO, JSONSerializableDTO, apigen_config
from parlant.core.agents import AgentId
from parlant.core.common import DefaultBaseModel
from parlant.core.context_variables import (
    ContextVariableId,
    ContextVariableStore,
    ContextVariableValueId,
    FreshnessRules,
)
from parlant.core.services.tools.service_registry import ServiceRegistry
from parlant.core.tools import ToolId

API_GROUP = "context-variables"


class DayOfWeekDTO(Enum):
    SUNDAY = "Sunday"
    MONDAY = "Monday"
    TUESDAY = "Tuesday"
    WEDNESDAY = "Wednesday"
    THURSDAY = "Thursday"
    FRIDAY = "Friday"
    SATURDAY = "Saturday"


class FreshnessRulesDTO(DefaultBaseModel):
    months: Optional[list[int]] = None
    days_of_month: Optional[list[int]] = None
    days_of_week: Optional[list[DayOfWeekDTO]] = None
    hours: Optional[list[int]] = None
    minutes: Optional[list[int]] = None
    seconds: Optional[list[int]] = None


class ContextVariableDTO(DefaultBaseModel):
    id: ContextVariableId
    name: str
    description: Optional[str] = None
    tool_id: Optional[ToolIdDTO] = None
    freshness_rules: Optional[FreshnessRulesDTO] = None


class ContextVariableCreationParamsDTO(DefaultBaseModel):
    name: str
    description: Optional[str] = None
    tool_id: Optional[ToolIdDTO] = None
    freshness_rules: Optional[FreshnessRulesDTO] = None


class ContextVariableDeletionResult(DefaultBaseModel):
    context_variable_id: ContextVariableId


class ContextVariableValueDTO(DefaultBaseModel):
    id: ContextVariableValueId
    last_modified: datetime
    data: JSONSerializableDTO


class ContextVariableValueUpdateParamsDTO(DefaultBaseModel):
    data: JSONSerializableDTO


class ContextVariableReadResult(DefaultBaseModel):
    context_variable: ContextVariableDTO
    key_value_pairs: Optional[dict[str, ContextVariableValueDTO]]


def _freshness_ruless_dto_to_freshness_rules(dto: FreshnessRulesDTO) -> FreshnessRules:
    return FreshnessRules(
        months=dto.months,
        days_of_month=dto.days_of_month,
        days_of_week=[dow.value for dow in dto.days_of_week] if dto.days_of_week else [],
        hours=dto.hours,
        minutes=dto.minutes,
        seconds=dto.seconds,
    )


def _freshness_ruless_to_dto(freshness_rules: FreshnessRules) -> FreshnessRulesDTO:
    return FreshnessRulesDTO(
        months=freshness_rules.months,
        days_of_month=freshness_rules.days_of_month,
        days_of_week=[DayOfWeekDTO(dow) for dow in freshness_rules.days_of_week]
        if freshness_rules.days_of_week
        else [],
        hours=freshness_rules.hours,
        minutes=freshness_rules.minutes,
        seconds=freshness_rules.seconds,
    )


def create_router(
    context_variable_store: ContextVariableStore,
    service_registry: ServiceRegistry,
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/{agent_id}/context-variables",
        status_code=status.HTTP_201_CREATED,
        operation_id="create_variable",
        **apigen_config(group_name=API_GROUP, method_name="create"),
    )
    async def create_variable(
        agent_id: AgentId,
        params: ContextVariableCreationParamsDTO,
    ) -> ContextVariableDTO:
        if params.tool_id:
            service = await service_registry.read_tool_service(params.tool_id.service_name)
            _ = await service.read_tool(params.tool_id.tool_name)

        variable = await context_variable_store.create_variable(
            variable_set=agent_id,
            name=params.name,
            description=params.description,
            tool_id=ToolId(params.tool_id.service_name, params.tool_id.tool_name)
            if params.tool_id
            else None,
            freshness_rules=_freshness_ruless_dto_to_freshness_rules(params.freshness_rules)
            if params.freshness_rules
            else None,
        )

        return ContextVariableDTO(
            id=variable.id,
            name=variable.name,
            description=variable.description,
            tool_id=ToolIdDTO(
                service_name=variable.tool_id.service_name, tool_name=variable.tool_id.tool_name
            )
            if variable.tool_id
            else None,
            freshness_rules=_freshness_ruless_to_dto(variable.freshness_rules)
            if variable.freshness_rules
            else None,
        )

    @router.delete(
        "/{agent_id}/context-variables",
        status_code=status.HTTP_204_NO_CONTENT,
        operation_id="delete_variables",
        **apigen_config(group_name=API_GROUP, method_name="delete_many"),
    )
    async def delete_all_variables(
        agent_id: AgentId,
    ) -> None:
        for v in await context_variable_store.list_variables(variable_set=agent_id):
            await context_variable_store.delete_variable(variable_set=agent_id, id=v.id)

    @router.delete(
        "/{agent_id}/context-variables/{variable_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        operation_id="delete_variable",
        **apigen_config(group_name=API_GROUP, method_name="delete"),
    )
    async def delete_variable(
        agent_id: AgentId,
        variable_id: ContextVariableId,
    ) -> None:
        await context_variable_store.read_variable(variable_set=agent_id, id=variable_id)

        await context_variable_store.delete_variable(variable_set=agent_id, id=variable_id)

    @router.get(
        "/{agent_id}/context-variables",
        operation_id="list_variables",
        **apigen_config(group_name=API_GROUP, method_name="list"),
    )
    async def list_variables(
        agent_id: AgentId,
    ) -> list[ContextVariableDTO]:
        variables = await context_variable_store.list_variables(variable_set=agent_id)

        return [
            ContextVariableDTO(
                id=variable.id,
                name=variable.name,
                description=variable.description,
                tool_id=ToolIdDTO(
                    service_name=variable.tool_id.service_name,
                    tool_name=variable.tool_id.tool_name,
                )
                if variable.tool_id
                else None,
                freshness_rules=_freshness_ruless_to_dto(variable.freshness_rules)
                if variable.freshness_rules
                else None,
            )
            for variable in variables
        ]

    @router.put(
        "/{agent_id}/context-variables/{variable_id}/{key}",
        operation_id="update_variable_value",
        **apigen_config(group_name=API_GROUP, method_name="set_value"),
    )
    async def update_variable_value(
        agent_id: AgentId,
        variable_id: ContextVariableId,
        key: str,
        params: ContextVariableValueUpdateParamsDTO,
    ) -> ContextVariableValueDTO:
        _ = await context_variable_store.read_variable(
            variable_set=agent_id,
            id=variable_id,
        )

        variable_value = await context_variable_store.update_value(
            variable_set=agent_id,
            key=key,
            variable_id=variable_id,
            data=params.data,
        )

        return ContextVariableValueDTO(
            id=variable_value.id,
            last_modified=variable_value.last_modified,
            data=cast(JSONSerializableDTO, variable_value.data),
        )

    @router.get(
        "/{agent_id}/context-variables/{variable_id}/{key}",
        operation_id="read_variable_value",
        **apigen_config(group_name=API_GROUP, method_name="get_value"),
    )
    async def read_variable_value(
        agent_id: AgentId,
        variable_id: ContextVariableId,
        key: str,
    ) -> ContextVariableValueDTO:
        _ = await context_variable_store.read_variable(
            variable_set=agent_id,
            id=variable_id,
        )

        variable_value = await context_variable_store.read_value(
            variable_set=agent_id,
            key=key,
            variable_id=variable_id,
        )

        if variable_value is not None:
            return ContextVariableValueDTO(
                id=variable_value.id,
                last_modified=variable_value.last_modified,
                data=cast(JSONSerializableDTO, variable_value.data),
            )

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    @router.get(
        "/{agent_id}/context-variables/{variable_id}",
        operation_id="read_variable",
        **apigen_config(group_name=API_GROUP, method_name="retrieve"),
    )
    async def read_variable(
        agent_id: AgentId,
        variable_id: ContextVariableId,
        include_values: bool = True,
    ) -> ContextVariableReadResult:
        variable = await context_variable_store.read_variable(
            variable_set=agent_id,
            id=variable_id,
        )

        variable_dto = ContextVariableDTO(
            id=variable.id,
            name=variable.name,
            description=variable.description,
            tool_id=ToolIdDTO(
                service_name=variable.tool_id.service_name,
                tool_name=variable.tool_id.tool_name,
            )
            if variable.tool_id
            else None,
            freshness_rules=_freshness_ruless_to_dto(variable.freshness_rules)
            if variable.freshness_rules
            else None,
        )

        if not include_values:
            return ContextVariableReadResult(
                context_variable=variable_dto,
                key_value_pairs=None,
            )

        key_value_pairs = await context_variable_store.list_values(
            variable_set=agent_id,
            variable_id=variable_id,
        )

        return ContextVariableReadResult(
            context_variable=variable_dto,
            key_value_pairs={
                key: ContextVariableValueDTO(
                    id=value.id,
                    last_modified=value.last_modified,
                    data=cast(JSONSerializableDTO, value.data),
                )
                for key, value in key_value_pairs
            },
        )

    @router.delete(
        "/{agent_id}/context-variables/{variable_id}/{key}",
        status_code=status.HTTP_204_NO_CONTENT,
        operation_id="delete_value",
        **apigen_config(group_name=API_GROUP, method_name="delete_value"),
    )
    async def delete_value(
        agent_id: AgentId,
        variable_id: ContextVariableId,
        key: str,
    ) -> None:
        await context_variable_store.read_variable(
            variable_set=agent_id,
            id=variable_id,
        )

        await context_variable_store.read_value(
            variable_set=agent_id,
            variable_id=variable_id,
            key=key,
        )

        await context_variable_store.delete_value(
            variable_set=agent_id,
            variable_id=variable_id,
            key=key,
        )

    return router
