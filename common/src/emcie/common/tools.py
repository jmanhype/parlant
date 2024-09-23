from dataclasses import dataclass, field
from datetime import datetime
from typing import (
    Awaitable,
    Callable,
    Literal,
    Mapping,
    NewType,
    Optional,
    TypedDict,
    Union,
)
from typing_extensions import NotRequired

from emcie.common.types.common import JSONSerializable


ToolId = NewType("ToolId", str)

ToolParameterType = Literal[
    "string",
    "number",
    "integer",
    "boolean",
]


class ToolParameter(TypedDict):
    type: ToolParameterType
    description: NotRequired[str]
    enum: NotRequired[list[Union[str, int, float, bool]]]


class ToolContext:
    def __init__(
        self,
        session_id: str,
        emit_message: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> None:  # noqa: F821
        self.session_id = session_id
        self._emit_message = emit_message

    async def emit_message(self, message: str) -> None:
        assert self._emit_message
        await self._emit_message(message)


@dataclass(frozen=True)
class ToolResult:
    data: JSONSerializable
    metadata: Mapping[str, JSONSerializable] = field(default_factory=dict)


@dataclass(frozen=True)
class Tool:
    id: ToolId
    creation_utc: datetime
    name: str
    description: str
    parameters: dict[str, ToolParameter]
    required: list[str]
    consequential: bool

    def __hash__(self) -> int:
        return hash(self.id)
