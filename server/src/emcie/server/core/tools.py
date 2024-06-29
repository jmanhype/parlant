from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, NewType, Optional
from pydantic import ValidationError

from emcie.server.core import common
from emcie.server.core.persistence import DocumentCollection  # Adjusted import

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
        tool_collection: DocumentCollection[Tool],
    ):
        self._collection = tool_collection

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
        if not await self._is_tool_name_unique(tool_set, name):
            raise ValidationError("Tool name must be unique within the tool set")

        tool = Tool(
            id=ToolId(common.generate_id()),
            creation_utc=creation_utc or datetime.now(timezone.utc),
            name=name,
            module_path=module_path,
            description=description,
            parameters=parameters,
            required=required,
            consequential=consequential,
        )
        return await self._collection.add_document(tool_set, tool.id, tool)

    async def list_tools(
        self,
        tool_set: str,
    ) -> Iterable[Tool]:
        return await self._collection.read_documents(tool_set)

    async def read_tool(
        self,
        tool_set: str,
        tool_id: ToolId,
    ) -> Tool:
        return await self._collection.read_document(tool_set, tool_id)

    async def _is_tool_name_unique(
        self,
        tool_set: str,
        name: str,
    ) -> bool:
        tools = await self.list_tools(tool_set)
        return all(tool.name != name for tool in tools)
