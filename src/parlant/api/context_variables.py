# Copyright 2024 Emcie Co Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from datetime import datetime
from enum import Enum
from fastapi import HTTPException, Path, Query, status
from typing import Annotated, Optional, TypeAlias, cast

from fastapi import APIRouter
from pydantic import Field
from parlant.api import common
from parlant.api.common import ToolIdDTO, JSONSerializableDTO, apigen_config, ExampleJson
from parlant.core.agents import AgentId
from parlant.core.common import DefaultBaseModel
from parlant.core.context_variables import (
    ContextVariableId,
    ContextVariableStore,
    ContextVariableUpdateParams,
    ContextVariableValueId,
    FreshnessRules,
)
from parlant.core.services.tools.service_registry import ServiceRegistry
from parlant.core.tools import ToolId

API_GROUP = "context-variables"


class DayOfWeekDTO(Enum):
    """Days of the week for freshness rules."""

    SUNDAY = "Sunday"
    MONDAY = "Monday"
    TUESDAY = "Tuesday"
    WEDNESDAY = "Wednesday"
    THURSDAY = "Thursday"
    FRIDAY = "Friday"
    SATURDAY = "Saturday"


class FreshnessRulesDTO(DefaultBaseModel):
    """Rules for validating data freshness."""

    months: Optional[list[int]] = Field(
        default=None,
        description="List of valid months (1-12)",
        examples=[[1, 6, 12]],
    )
    days_of_month: Optional[list[int]] = Field(
        default=None,
        description="List of valid days of month (1-31)",
        examples=[[1, 15, 30]],
    )
    days_of_week: Optional[list[DayOfWeekDTO]] = Field(
        default=None,
        description="List of valid days of week",
        examples=[["Monday", "Wednesday", "Friday"]],
    )
    hours: Optional[list[int]] = Field(
        default=None,
        description="List of valid hours (0-23)",
        examples=[[9, 13, 17]],
    )
    minutes: Optional[list[int]] = Field(
        default=None,
        description="List of valid minutes (0-59)",
        examples=[[0, 30]],
    )
    seconds: Optional[list[int]] = Field(
        default=None,
        description="List of valid seconds (0-59)",
        examples=[[0, 30]],
    )


ContextVariableIdPath: TypeAlias = Annotated[
    ContextVariableId,
    Path(
        description="Unique identifier for the context variable",
        examples=["v9a8r7i6b5"],
    ),
]


ContextVariableNameField: TypeAlias = Annotated[
    str,
    Field(
        description="Name of the context variable",
        examples=["balance"],
        min_length=1,
    ),
]

ContextVariableDescriptionField: TypeAlias = Annotated[
    str,
    Field(
        description="Description of the context variable's purpose",
        examples=["Stores user preferences for customized interactions"],
    ),
]


FreshnessRulesField: TypeAlias = Annotated[
    FreshnessRulesDTO,
    Field(
        description="Rules for data freshness validation",
    ),
]

context_variable_example = {
    "id": "v9a8r7i6b5",
    "name": "UserBalance",
    "description": "Stores the account balances of users",
    "tool_id": {
        "service_name": "finance_service",
        "tool_name": "balance_checker",
    },
    "freshness_rules": {
        "months": [1, 6, 12],
        "days_of_month": [1, 15, 30],
        "days_of_week": ["Monday", "Wednesday", "Friday"],
        "hours": [9, 13, 17],
        "minutes": [0, 30],
        "seconds": [0, 30],
    },
}


class ContextVariableDTO(
    DefaultBaseModel,
    json_schema_extra={"example": context_variable_example},
):
    """
    Represents a type of customer or tag data that the agent tracks.

    Context variables store information that helps the agent provide
    personalized responses based on each customer's or group's specific situation,
    such as their subscription tier, usage patterns, or preferences.
    """

    id: ContextVariableIdPath
    name: ContextVariableNameField
    description: Optional[ContextVariableDescriptionField] = None
    tool_id: Optional[ToolIdDTO] = None
    freshness_rules: Optional[FreshnessRulesField] = None


context_variable_creation_params_example = {
    "name": "UserBalance",
    "description": "Stores the account balances of users",
    "tool_id": {
        "service_name": "finance_service",
        "tool_name": "balance_checker",
    },
    "freshness_rules": {
        "months": [1, 6, 12],
        "days_of_month": [1, 15, 30],
        "days_of_week": ["Monday", "Wednesday", "Friday"],
        "hours": [9, 13, 17],
        "minutes": [0, 30],
        "seconds": [0, 30],
    },
}


class ContextVariableCreationParamsDTO(
    DefaultBaseModel,
    json_schema_extra={"example": context_variable_creation_params_example},
):
    """Parameters for creating a new context variable."""

    name: ContextVariableNameField
    description: Optional[ContextVariableDescriptionField] = None
    tool_id: Optional[ToolIdDTO] = None
    freshness_rules: Optional[FreshnessRulesField] = None


context_variable_update_params_example = {
    "name": "CustomerBalance",
    "freshness_rules": {
        "hours": [8, 12, 16],
        "minutes": [0],
    },
}


class ContextVariableUpdateParamsDTO(
    DefaultBaseModel,
    json_schema_extra={"example": context_variable_update_params_example},
):
    """Parameters for updating an existing context variable."""

    name: Optional[ContextVariableNameField] = None
    description: Optional[ContextVariableDescriptionField] = None
    tool_id: Optional[ToolIdDTO] = None
    freshness_rules: Optional[FreshnessRulesField] = None


ValueIdField: TypeAlias = Annotated[
    ContextVariableValueId,
    Field(
        description="Unique identifier for the variable value",
        examples=["val_789abc"],
    ),
]

LastModifiedField: TypeAlias = Annotated[
    datetime,
    Field(
        description="Timestamp of the last modification",
    ),
]


DataField: TypeAlias = Annotated[
    JSONSerializableDTO,
    Field(
        description="The actual data stored in the variable",
    ),
]


class ContextVariableValueDTO(DefaultBaseModel):
    """
    Represents the actual stored value for a specific customer's or tag's context.

    This could be their subscription details, feature usage history,
    preferences, or any other customer or tag information that helps
    personalize the agent's responses.
    """

    id: ValueIdField
    last_modified: LastModifiedField
    data: DataField


class ContextVariableValueUpdateParamsDTO(DefaultBaseModel):
    """Parameters for updating a context variable value."""

    data: DataField


KeyValuePairsField: TypeAlias = Annotated[
    dict[str, ContextVariableValueDTO],
    Field(
        description="Collection of key-value pairs associated with the variable",
    ),
]


class ContextVariableReadResult(DefaultBaseModel):
    """Complete context variable data including its values."""

    context_variable: ContextVariableDTO
    key_value_pairs: Optional[KeyValuePairsField] = None


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


AgentIdPath: TypeAlias = Annotated[
    AgentId,
    Path(
        description="Unique identifier of the agent",
        examples=["a1g2e3n4t5"],
    ),
]

ContextVariableKeyPath: TypeAlias = Annotated[
    str,
    Path(
        description="Key for the variable value",
        examples=["user_1", "tag_vip"],
        min_length=1,
    ),
]


IncludeValuesQuery: TypeAlias = Annotated[
    bool,
    Query(
        description="Whether to include variable values in the response",
        examples=[True, False],
    ),
]


context_variable_value_example: ExampleJson = {
    "id": "v5a4lb3c9",
    "last_modified": "2024-03-20T14:30:00Z",
    "data": {
        "subscription": "standard",
    },
}


context_variable_read_result_example: ExampleJson = {
    "context_variable": context_variable_example,
    "key_value_pairs": {
        "customer_123": context_variable_value_example,
        "tag:vip": {
            "id": "val_456def",
            "last_modified": "2024-04-15T10:00:00Z",
            "data": {
                "subscription": "premium",
            },
        },
    },
}


def create_router(
    context_variable_store: ContextVariableStore,
    service_registry: ServiceRegistry,
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/{agent_id}/context-variables",
        status_code=status.HTTP_201_CREATED,
        operation_id="create_variable",
        response_model=ContextVariableDTO,
        responses={
            status.HTTP_201_CREATED: {
                "description": "Context variable type successfully created",
                "content": common.example_json_content(context_variable_example),
            },
            status.HTTP_404_NOT_FOUND: {"description": "Agent or tool not found"},
            status.HTTP_422_UNPROCESSABLE_ENTITY: {
                "description": "Validation error in request parameters"
            },
        },
        **apigen_config(group_name=API_GROUP, method_name="create"),
    )
    async def create_variable(
        agent_id: AgentIdPath,
        params: ContextVariableCreationParamsDTO,
    ) -> ContextVariableDTO:
        """
        Creates a new context variable for tracking customer-specific or tag-specific data.

        Example uses:
        - Track subscription tiers to control feature access
        - Store usage patterns for personalized recommendations
        - Remember customer preferences for tailored responses
        """
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

    @router.patch(
        "/{agent_id}/context-variables/{variable_id}",
        operation_id="update_variable",
        response_model=ContextVariableDTO,
        responses={
            status.HTTP_200_OK: {
                "description": "Context variable type successfully updated",
                "content": common.example_json_content(context_variable_example),
            },
            status.HTTP_404_NOT_FOUND: {"description": "Variable or agent not found"},
            status.HTTP_422_UNPROCESSABLE_ENTITY: {
                "description": "Validation error in request parameters"
            },
        },
        **apigen_config(group_name=API_GROUP, method_name="update"),
    )
    async def update_variable(
        agent_id: AgentIdPath,
        variable_id: ContextVariableIdPath,
        params: ContextVariableUpdateParamsDTO,
    ) -> ContextVariableDTO:
        """
        Updates an existing context variable.

        Only provided fields will be updated; others remain unchanged.
        """

        def from_dto(dto: ContextVariableUpdateParamsDTO) -> ContextVariableUpdateParams:
            params: ContextVariableUpdateParams = {}

            if dto.name:
                params["name"] = dto.name

            if dto.description:
                params["description"] = dto.description

            if dto.tool_id:
                params["tool_id"] = ToolId(
                    service_name=dto.tool_id.service_name, tool_name=dto.tool_id.tool_name
                )

            if dto.freshness_rules:
                params["freshness_rules"] = _freshness_ruless_dto_to_freshness_rules(
                    dto.freshness_rules
                )

            return params

        variable = await context_variable_store.update_variable(
            variable_set=agent_id,
            id=variable_id,
            params=from_dto(params),
        )

        return ContextVariableDTO(
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

    @router.delete(
        "/{agent_id}/context-variables",
        status_code=status.HTTP_204_NO_CONTENT,
        operation_id="delete_variables",
        responses={
            status.HTTP_204_NO_CONTENT: {"description": "All context variables deleted"},
            status.HTTP_404_NOT_FOUND: {"description": "Agent not found"},
        },
        **apigen_config(group_name=API_GROUP, method_name="delete_many"),
    )
    async def delete_all_variables(
        agent_id: AgentIdPath,
    ) -> None:
        """Deletes all context variables and their values for the provided agent ID"""
        for v in await context_variable_store.list_variables(variable_set=agent_id):
            await context_variable_store.delete_variable(variable_set=agent_id, id=v.id)

    @router.delete(
        "/{agent_id}/context-variables/{variable_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        operation_id="delete_variable",
        responses={
            status.HTTP_204_NO_CONTENT: {
                "description": "Context variable and all its values deleted"
            },
            status.HTTP_404_NOT_FOUND: {"description": "Variable or agent not found"},
        },
        **apigen_config(group_name=API_GROUP, method_name="delete"),
    )
    async def delete_variable(
        agent_id: AgentIdPath,
        variable_id: ContextVariableIdPath,
    ) -> None:
        """
        Deletes a specific context variable and all its values.
        """
        await context_variable_store.read_variable(variable_set=agent_id, id=variable_id)

        await context_variable_store.delete_variable(variable_set=agent_id, id=variable_id)

    @router.get(
        "/{agent_id}/context-variables",
        operation_id="list_variables",
        response_model=list[ContextVariableDTO],
        responses={
            status.HTTP_200_OK: {
                "description": "List of all context variable for the provided agent",
                "content": common.example_json_content([context_variable_example]),
            },
            status.HTTP_404_NOT_FOUND: {"description": "Agent not found"},
        },
        **apigen_config(group_name=API_GROUP, method_name="list"),
    )
    async def list_variables(
        agent_id: AgentIdPath,
    ) -> list[ContextVariableDTO]:
        """Lists all context variables set for the provided agent"""
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
        response_model=ContextVariableValueDTO,
        responses={
            status.HTTP_200_OK: {
                "description": "Context value successfully updated for the customer or tag",
                "content": common.example_json_content(context_variable_value_example),
            },
            status.HTTP_404_NOT_FOUND: {"description": "Variable, agent, or key not found"},
            status.HTTP_422_UNPROCESSABLE_ENTITY: {
                "description": "Validation error in request parameters"
            },
        },
        **apigen_config(group_name=API_GROUP, method_name="set_value"),
    )
    async def update_variable_value(
        agent_id: AgentIdPath,
        variable_id: ContextVariableIdPath,
        key: ContextVariableKeyPath,
        params: ContextVariableValueUpdateParamsDTO,
    ) -> ContextVariableValueDTO:
        """
        Updates the value of a context variable.

        The key represents a customer identifier or a customer tag in the format `tag:{tag_id}`.
        The data contains the actual context information being stored.
        """
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
        response_model=ContextVariableValueDTO,
        responses={
            status.HTTP_200_OK: {
                "description": "Retrieved context value for the customer or tag",
                "content": common.example_json_content(context_variable_value_example),
            },
            status.HTTP_404_NOT_FOUND: {"description": "Variable, agent, or key not found"},
        },
        **apigen_config(group_name=API_GROUP, method_name="get_value"),
    )
    async def read_variable_value(
        agent_id: AgentIdPath,
        variable_id: ContextVariableIdPath,
        key: ContextVariableKeyPath,
    ) -> ContextVariableValueDTO:
        """
        Retrieves the value of a context variable for a specific customer or tag.

        The key should be a customer identifier or a customer tag in the format `tag:{tag_id}`.
        """
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
        response_model=ContextVariableReadResult,
        responses={
            status.HTTP_200_OK: {
                "description": "Context variable details with optional values",
                "content": common.example_json_content(context_variable_read_result_example),
            },
            status.HTTP_404_NOT_FOUND: {"description": "Variable or agent not found"},
            status.HTTP_422_UNPROCESSABLE_ENTITY: {
                "description": "Validation error in request parameters"
            },
        },
        **apigen_config(group_name=API_GROUP, method_name="retrieve"),
    )
    async def read_variable(
        agent_id: AgentIdPath,
        variable_id: ContextVariableIdPath,
        include_values: IncludeValuesQuery = True,
    ) -> ContextVariableReadResult:
        """
        Retrieves a context variable's details and optionally its values.

        Can return all customer or tag values for this variable type if include_values=True.
        """
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
        responses={
            status.HTTP_204_NO_CONTENT: {
                "description": "Context value deleted for the customer or tag"
            },
            status.HTTP_404_NOT_FOUND: {"description": "Variable, agent, or key not found"},
        },
        **apigen_config(group_name=API_GROUP, method_name="delete_value"),
    )
    async def delete_value(
        agent_id: AgentIdPath,
        variable_id: ContextVariableIdPath,
        key: ContextVariableKeyPath,
    ) -> None:
        """
        Deletes a specific customer's or tag's value for this context variable.

        The key should be a customer identifier or a customer tag in the format `tag:{tag_id}`.
        Removes only the value for the specified key while keeping the variable's configuration.
        """
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
