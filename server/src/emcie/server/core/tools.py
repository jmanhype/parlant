from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, NewType, Optional

from pydantic import ValidationError

from emcie.server.core import common
from emcie.server.core.persistence import DocumentDatabase, FieldFilter

ToolId = NewType("ToolId", str)


@dataclass(frozen=True)
class Tool:
    id: ToolId
    creation_utc: datetime
    name: str
    module_path: str
    description: str
    parameters: dict[str, Any]
    required: list[str]
    consequential: bool

    def __hash__(self) -> int:
        return hash(self.id)


class ToolStore(ABC):
    @abstractmethod
    async def create_tool(
        self,
        tool_set: str,
        name: str,
        module_path: str,
        description: str,
        parameters: dict[str, Any],
        required: list[str],
        creation_utc: Optional[datetime] = None,
        consequential: bool = False,
    ) -> Tool: ...

    @abstractmethod
    async def list_tools(
        self,
        tool_set: str,
    ) -> Iterable[Tool]: ...

    @abstractmethod
    async def read_tool(
        self,
        tool_set: str,
        tool_id: ToolId,
    ) -> Tool: ...


class ToolDocumentStore(ToolStore):
    def __init__(
        self,
        database: DocumentDatabase,
    ) -> None:
        self._database = database
        self._collection_name = "tools"

    async def create_tool(
        self,
        tool_set: str,
        name: str,
        module_path: str,
        description: str,
        parameters: dict[str, Any],
        required: list[str],
        creation_utc: Optional[datetime] = None,
        consequential: bool = False,
    ) -> Tool:
        if list(
            await self._database.find(
                collection=self._collection_name, filters={"name": FieldFilter(equal_to=name)}
            )
        ):
            raise ValidationError("Tool name must be unique within the tool set")

        tool_data = {
            "tool_set": tool_set,
            "name": name,
            "module_path": module_path,
            "description": description,
            "parameters": parameters,
            "required": required,
            "creation_utc": creation_utc or datetime.now(timezone.utc),
            "consequential": consequential,
        }
        inserted_tool = await self._database.insert_one(self._collection_name, tool_data)
        return common.create_instance_from_dict(Tool, inserted_tool)

    async def list_tools(
        self,
        tool_set: str,
    ) -> Iterable[Tool]:
        filters = {"tool_set": FieldFilter(equal_to=tool_set)}
        tools = await self._database.find(self._collection_name, filters)
        return (common.create_instance_from_dict(Tool, tool) for tool in tools)

    async def read_tool(
        self,
        tool_set: str,
        tool_id: ToolId,
    ) -> Tool:
        filters = {
            "tool_set": FieldFilter(equal_to=tool_set),
            "id": FieldFilter(equal_to=tool_id),
        }
        tool = await self._database.find_one(self._collection_name, filters)
        return common.create_instance_from_dict(Tool, tool)
