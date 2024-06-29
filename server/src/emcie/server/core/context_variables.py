from abc import ABC, abstractmethod
from typing import Iterable, Literal, NewType, Optional
from datetime import datetime, timezone
from dataclasses import dataclass

from emcie.server.core.common import JSONSerializable, generate_id
from emcie.server.core.tools import ToolId
from emcie.server.core.persistence import DocumentCollection

ContextVariableId = NewType("ContextVariableId", str)
ContextVariableValueId = NewType("ContextVariableValueId", str)


@dataclass(frozen=True)
class FreshnessRules:
    months: Optional[list[int]] = None
    days_of_month: Optional[list[int]] = None
    days_of_week: Optional[
        list[Literal["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]]
    ] = None
    hours: Optional[list[int]] = None
    minutes: Optional[list[int]] = None
    seconds: Optional[list[int]] = None


@dataclass(frozen=True)
class ContextVariable:
    id: ContextVariableId
    name: str
    description: Optional[str]
    tool_id: ToolId
    freshness_rules: Optional[FreshnessRules]


@dataclass(frozen=True)
class ContextVariableValue:
    id: ContextVariableValueId
    variable_id: ContextVariableId
    last_modified: datetime
    data: JSONSerializable


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
        data: JSONSerializable,
    ) -> ContextVariableValue: ...

    @abstractmethod
    async def delete_variable(
        self,
        variable_set: str,
        variable_id: ContextVariableId,
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
        variable_id: ContextVariableId,
    ) -> ContextVariable: ...

    @abstractmethod
    async def read_value(
        self,
        variable_set: str,
        key: str,
        variable_id: ContextVariableId,
    ) -> ContextVariableValue: ...


class ContextVariableDocumentStore(ContextVariableStore):
    def __init__(
        self,
        variable_collection: DocumentCollection[ContextVariable],
        value_collection: DocumentCollection[ContextVariableValue],
    ):
        self.variable_collection = variable_collection
        self.value_collection = value_collection

    async def create_variable(
        self,
        variable_set: str,
        name: str,
        description: Optional[str],
        tool_id: ToolId,
        freshness_rules: Optional[FreshnessRules],
    ) -> ContextVariable:
        variable = ContextVariable(
            id=ContextVariableId(generate_id()),
            name=name,
            description=description,
            tool_id=tool_id,
            freshness_rules=freshness_rules,
        )
        await self.variable_collection.add_document(variable_set, variable.id, variable)
        return variable

    async def update_value(
        self,
        variable_set: str,
        key: str,
        variable_id: ContextVariableId,
        data: JSONSerializable,
    ) -> ContextVariableValue:
        updated_value = ContextVariableValue(
            id=ContextVariableValueId(generate_id()),
            variable_id=variable_id,
            last_modified=datetime.now(timezone.utc),
            data=data,
        )
        combined_key = f"{key}_{variable_id}"
        await self.value_collection.add_document(variable_set, combined_key, updated_value)
        return updated_value

    async def delete_variable(
        self,
        variable_set: str,
        variable_id: ContextVariableId,
    ) -> None:
        await self.variable_collection.delete_document(variable_set, variable_id)

    async def list_variables(
        self,
        variable_set: str,
    ) -> Iterable[ContextVariable]:
        return await self.variable_collection.read_documents(variable_set)

    async def read_variable(
        self,
        variable_set: str,
        variable_id: ContextVariableId,
    ) -> ContextVariable:
        return await self.variable_collection.read_document(variable_set, variable_id)

    async def read_value(
        self,
        variable_set: str,
        key: str,
        variable_id: ContextVariableId,
    ) -> ContextVariableValue:
        combined_key = f"{key}_{variable_id}"
        return await self.value_collection.read_document(variable_set, combined_key)
