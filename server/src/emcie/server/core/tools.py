from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, NewType, Optional

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


class ToolStore:
    def __init__(
        self,
    ) -> None:
        self._tool_sets: dict[str, dict[ToolId, Tool]] = defaultdict(dict)

    async def create_tool(
        self,
        tool_set: str,
        name: str,
        module_path: str,
        description: str,
        parameters: dict[str, Any],
        required: list[str],
        creation_utc: Optional[datetime] = None,
    ) -> Tool:
        tool = Tool(
            id=ToolId(common.generate_id()),
            name=name,
            module_path=module_path,
            description=description,
            creation_utc=creation_utc or datetime.now(timezone.utc),
            parameters=parameters,
            required=required,
        )

        self._tool_sets[tool_set][tool.id] = tool

        return tool

    async def list_tools(
        self,
        tool_set: str,
    ) -> Iterable[Tool]:
        return self._tool_sets[tool_set].values()
