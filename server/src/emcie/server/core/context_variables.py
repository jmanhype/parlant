from abc import ABC, abstractmethod
from typing import Any, Iterable, Literal, NewType, Optional
from datetime import datetime, timezone
from dataclasses import dataclass

from emcie.server.base_models import DefaultBaseModel
from emcie.server.core import common
from emcie.server.core.tools import ToolId
from emcie.server.core.persistence import CollectionDescriptor, DocumentDatabase, FieldFilter

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


context_variable_schema = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": ["string", "null"]},
        "tool_id": {"type": "string"},
        "freshness_rules": {"type": "string"},
    },
    "required": ["id", "name", "tool_id"],
}


@dataclass(frozen=True)
class ContextVariableValue:
    id: ContextVariableValueId
    variable_id: ContextVariableId
    last_modified: datetime
    data: common.JSONSerializable


context_variable_value_schema = context_variable_schema = {
    "definitions": {
        "FreshnessRules": {
            "type": "object",
            "properties": {
                "months": {"type": ["array", "null"], "items": {"type": "integer"}},
                "days_of_month": {"type": ["array", "null"], "items": {"type": "integer"}},
                "days_of_week": {
                    "type": ["array", "null"],
                    "items": {
                        "type": "string",
                        "enum": [
                            "Sunday",
                            "Monday",
                            "Tuesday",
                            "Wednesday",
                            "Thursday",
                            "Friday",
                            "Saturday",
                        ],
                    },
                },
                "hours": {"type": ["array", "null"], "items": {"type": "integer"}},
                "minutes": {"type": ["array", "null"], "items": {"type": "integer"}},
                "seconds": {"type": ["array", "null"], "items": {"type": "integer"}},
            },
            "additionalProperties": False,
        }
    },
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": ["string", "null"]},
        "tool_id": {"type": "string"},
        "freshness_rules": {"type": ["object", "null"], "$ref": "#/definitions/FreshnessRules"},
    },
    "required": ["id", "name", "tool_id"],
}


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
    class ContextVariableDocument(DefaultBaseModel):
        id: str
        variable_set: str
        name: str
        description: Optional[str] = None
        tool_id: ToolId
        freshness_rules: Optional[FreshnessRules]

    class ContextVariableValueDocument(DefaultBaseModel):
        id: str
        last_modified: datetime
        variable_set: str
        variable_id: ContextVariableId
        key: str
        data: dict[str, Any]

    def __init__(self, database: DocumentDatabase):
        self._database = database
        self._variable_collection = CollectionDescriptor(
            name="variables",
            schema=self.ContextVariableDocument,
        )
        self._value_collection = CollectionDescriptor(
            name="values",
            schema=self.ContextVariableValueDocument,
        )

    async def create_variable(
        self,
        variable_set: str,
        name: str,
        description: Optional[str],
        tool_id: ToolId,
        freshness_rules: Optional[FreshnessRules],
    ) -> ContextVariable:
        variable_document = await self._database.insert_one(
            self._variable_collection,
            {
                "id": common.generate_id(),
                "variable_set": variable_set,
                "name": name,
                "description": description,
                "tool_id": tool_id,
                "freshness_rules": freshness_rules,
            },
        )
        return ContextVariable(
            id=variable_document["id"],
            name=name,
            description=description,
            tool_id=tool_id,
            freshness_rules=freshness_rules,
        )

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
        value_document = await self._database.update_one(
            self._value_collection,
            filters,
            {
                "id": common.generate_id(),
                "variable_set": variable_set,
                "variable_id": variable_id,
                "last_modified": datetime.now(timezone.utc),
                "data": data,
                "key": key,
            },
            upsert=True,
        )
        return ContextVariableValue(
            id=ContextVariableValueId(value_document["id"]),
            variable_id=variable_id,
            last_modified=value_document["last_modified"],
            data=data,
        )

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

        return (
            ContextVariable(
                id=ContextVariableId(d["id"]),
                name=d["name"],
                description=d["description"],
                tool_id=d["tool_id"],
                freshness_rules=d["freshness_rules"],
            )
            for d in await self._database.find(self._variable_collection, filters)
        )

    async def read_variable(
        self,
        variable_set: str,
        id: ContextVariableId,
    ) -> ContextVariable:
        filters = {
            "variable_set": FieldFilter(equal_to=variable_set),
            "id": FieldFilter(equal_to=id),
        }

        variable_document = await self._database.find_one(self._variable_collection, filters)
        return ContextVariable(
            id=ContextVariableId(variable_document["id"]),
            name=variable_document["name"],
            description=variable_document["description"],
            tool_id=variable_document["tool_id"],
            freshness_rules=variable_document["freshness_rules"],
        )

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
        value_document = await self._database.find_one(self._value_collection, filters)
        return ContextVariableValue(
            id=ContextVariableValueId(value_document["id"]),
            variable_id=value_document["variable_id"],
            last_modified=value_document["last_modified"],
            data=value_document["data"],
        )
