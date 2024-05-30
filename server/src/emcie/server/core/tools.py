from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, NewType, Optional

from pydantic import ValidationError

from emcie.server.core import common

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


class ToolStore:
    def __init__(
        self,
    ) -> None:
        self._tool_sets: dict[str, dict[ToolId, Tool]] = defaultdict(dict)

    async def is_tool_name_unique(
        self,
        tool_set: str,
        name: str,
    ) -> bool:
        tools = await self.list_tools(tool_set)
        return all(tool.name != name for tool in tools)

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
        if not await self.is_tool_name_unique(tool_set, name):
            raise ValidationError("Tool name must be unique")

        tool = Tool(
            id=ToolId(common.generate_id()),
            name=name,
            module_path=module_path,
            description=description,
            creation_utc=creation_utc or datetime.now(timezone.utc),
            parameters=parameters,
            required=required,
            consequential=consequential,
        )

        self._tool_sets[tool_set][tool.id] = tool

        return tool

    async def list_tools(
        self,
        tool_set: str,
    ) -> Iterable[Tool]:
        return self._tool_sets[tool_set].values()
