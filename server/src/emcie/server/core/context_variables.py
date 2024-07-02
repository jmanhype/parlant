from abc import ABC, abstractmethod
from typing import Iterable, Literal, NewType, Optional
from datetime import datetime, timezone
from dataclasses import dataclass

from emcie.server.core import common
from emcie.server.core.tools import ToolId
from emcie.server.core.persistence import DocumentDatabase, FieldFilter

ContextVariableId = NewType("ContextVariableId", str)
ContextVariableValueId = NewType("ContextVariableValueId", str)


@dataclass(frozen=True)
class FreshnessRules:
    """
    A data class representing the times at which the context variable should be considered fresh.
    """

    months: Optional[list[int]]
    days_of_month: Optional[list[int]]
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
    ]
    hours: Optional[list[int]]
    minutes: Optional[list[int]]
    seconds: Optional[list[int]]


@dataclass(frozen=True)
class ContextVariable:
    id: ContextVariableId
    name: str
    description: Optional[str]
    tool_id: ToolId
    freshness_rules: Optional[FreshnessRules]
    """If None, the variable will only be updated on session creation"""


@dataclass(frozen=True)
class ContextVariableValue:
    id: ContextVariableValueId
    variable_id: ContextVariableId
    last_modified: datetime
    data: common.JSONSerializable


class ContextVariableStore(ABC):
    @abstractmethod
    async def create_variable(
        self,
        variable_set: str,
        name: str,
        description: Optional[str],
        tool_id: ToolId,
        freshness_rules: Optional[FreshnessRules],
    ) -> ContextVariable: ...

    @abstractmethod
    async def update_value(
        self,
        variable_set: str,
        key: str,
        variable_id: ContextVariableId,
        data: common.JSONSerializable,
    ) -> ContextVariableValue: ...

    @abstractmethod
    async def delete_variable(
        self,
        variable_set: str,
        id: ContextVariableId,
    ) -> None: ...

    @abstractmethod
    async def list_variables(
        self,
        variable_set: str,
    ) -> Iterable[ContextVariable]: ...

    @abstractmethod
    async def read_variable(
        self,
        variable_set: str,
        id: ContextVariableId,
    ) -> ContextVariable: ...

    @abstractmethod
    async def read_value(
        self,
        variable_set: str,
        key: str,
        variable_id: ContextVariableId,
    ) -> ContextVariableValue: ...


class ContextVariableDocumentStore(ContextVariableStore):
    def __init__(self, database: DocumentDatabase):
        self._database = database
        self._variable_collection = "variables"
        self._value_collection = "values"

    async def create_variable(
        self,
        variable_set: str,
        name: str,
        description: Optional[str],
        tool_id: ToolId,
        freshness_rules: Optional[FreshnessRules],
    ) -> ContextVariable:
        variable = {
            "variable_set": variable_set,
            "name": name,
            "description": description,
            "tool_id": tool_id,
            "freshness_rules": freshness_rules,
        }
        inserted_variable = await self._database.insert_one(self._variable_collection, variable)
        return common.create_instance_from_dict(ContextVariable, inserted_variable)

    async def update_value(
        self,
        variable_set: str,
        key: str,
        variable_id: ContextVariableId,
        data: common.JSONSerializable,
    ) -> ContextVariableValue:
        filters = {
            "variable_set": FieldFilter(equal_to=variable_set),
            "variable_id": FieldFilter(equal_to=variable_id),
            "key": FieldFilter(equal_to=key),
        }
        value_data = {
            "variable_set": variable_set,
            "variable_id": variable_id,
            "last_modified": datetime.now(timezone.utc),
            "data": data,
            "key": key,
        }
        updated_value = await self._database.update_one(
            self._value_collection, filters, value_data, upsert=True
        )
        return common.create_instance_from_dict(ContextVariableValue, updated_value)

    async def delete_variable(
        self,
        variable_set: str,
        id: ContextVariableId,
    ) -> None:
        filters = {
            "id": FieldFilter(equal_to=id),
            "variable_set": FieldFilter(equal_to=variable_set),
        }
        await self._database.delete_one(self._variable_collection, filters)

        filters = {
            "variable_id": FieldFilter(equal_to=id),
            "variable_set": FieldFilter(equal_to=variable_set),
        }
        await self._database.delete_one(self._value_collection, filters)

    async def list_variables(
        self,
        variable_set: str,
    ) -> Iterable[ContextVariable]:
        filters = {"variable_set": FieldFilter(equal_to=variable_set)}
        variables = await self._database.find(self._variable_collection, filters)
        return (common.create_instance_from_dict(ContextVariable, var) for var in variables)

    async def read_variable(
        self,
        variable_set: str,
        id: ContextVariableId,
    ) -> ContextVariable:
        filters = {
            "variable_set": FieldFilter(equal_to=variable_set),
            "id": FieldFilter(equal_to=id),
        }
        variable = await self._database.find_one(self._variable_collection, filters)
        return common.create_instance_from_dict(ContextVariable, variable)

    async def read_value(
        self,
        variable_set: str,
        key: str,
        variable_id: ContextVariableId,
    ) -> ContextVariableValue:
        filters = {
            "variable_set": FieldFilter(equal_to=variable_set),
            "variable_id": FieldFilter(equal_to=variable_id),
            "key": FieldFilter(equal_to=key),
        }
        value = await self._database.find_one(self._value_collection, filters)
        return common.create_instance_from_dict(ContextVariableValue, value)
