from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
import importlib
import inspect
from typing import Mapping, NamedTuple, Optional, Sequence

from emcie.common.tools import ToolResult, Tool, ToolContext, ToolParameter
from emcie.server.core.common import (
    JSONSerializable,
)


class ToolId(NamedTuple):
    service_name: str
    tool_name: str


class ToolError(Exception):
    def __init__(
        self,
        service_name: str,
        tool_name: str,
        message: Optional[str] = None,
    ) -> None:
        if message:
            super().__init__(
                f"Tool error (service='{service_name}', tool='{tool_name}'): {message}"
            )
        else:
            super().__init__(f"Tool error (service='{service_name}', tool='{tool_name}')")

        self.service_name = service_name
        self.tool_name = tool_name


class ToolImportError(ToolError):
    pass


class ToolExecutionError(ToolError):
    pass


class ToolResultError(ToolError):
    pass


class ToolService(ABC):
    @abstractmethod
    async def list_tools(
        self,
    ) -> Sequence[Tool]: ...

    @abstractmethod
    async def read_tool(
        self,
        name: str,
    ) -> Tool: ...

    @abstractmethod
    async def call_tool(
        self,
        name: str,
        context: ToolContext,
        arguments: Mapping[str, JSONSerializable],
    ) -> ToolResult: ...


@dataclass(frozen=True)
class _LocalTool:
    name: str
    creation_utc: datetime
    module_path: str
    description: str
    parameters: dict[str, ToolParameter]
    required: list[str]
    consequential: bool


class _LocalToolService(ToolService):
    def __init__(
        self,
    ) -> None:
        self._service_name = "_local"
        self._local_tools_by_name: dict[str, _LocalTool] = {}

    def _local_tool_to_tool(self, local: _LocalTool) -> Tool:
        return Tool(
            creation_utc=local.creation_utc,
            name=local.name,
            description=local.description,
            parameters=local.parameters,
            required=local.required,
            consequential=local.consequential,
        )

    async def create_tool(
        self,
        name: str,
        module_path: str,
        description: str,
        parameters: Mapping[str, ToolParameter],
        required: Sequence[str],
        consequential: bool = False,
    ) -> Tool:
        creation_utc = datetime.now(timezone.utc)

        local = _LocalTool(
            name=name,
            module_path=module_path,
            description=description,
            parameters=dict(parameters),
            creation_utc=creation_utc,
            required=list(required),
            consequential=consequential,
        )

        self._local_tools_by_name[name] = local

        return self._local_tool_to_tool(local)

    async def list_tools(
        self,
    ) -> Sequence[Tool]:
        return [self._local_tool_to_tool(local) for local in self._local_tools_by_name.values()]

    async def read_tool(
        self,
        name: str,
    ) -> Tool:
        return self._local_tool_to_tool(self._local_tools_by_name[name])

    async def call_tool(
        self,
        name: str,
        context: ToolContext,
        arguments: Mapping[str, JSONSerializable],
    ) -> ToolResult:
        _ = context

        try:
            local_tool = self._local_tools_by_name[name]
            module = importlib.import_module(local_tool.module_path)
            func = getattr(module, local_tool.name)
        except Exception as e:
            raise ToolImportError(self._service_name, name) from e

        try:
            result: ToolResult = func(**arguments)

            if inspect.isawaitable(result):
                result = await result
        except Exception as e:
            raise ToolExecutionError(self._service_name, name) from e

        if not isinstance(result, ToolResult):
            raise ToolResultError(
                self._service_name, name, "Tool result is not an instance of ToolResult"
            )

        return result
