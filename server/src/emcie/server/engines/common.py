from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterable, NewType

from emcie.server.core.agents import AgentId
from emcie.server.core.sessions import EventSource, SessionId


@dataclass(frozen=True)
class Context:
    session_id: SessionId
    agent_id: AgentId


@dataclass(frozen=True)
class ProducedEvent:
    source: EventSource
    type: str
    data: dict[str, Any]


class Engine(ABC):
    @abstractmethod
    async def process(
        self,
        context: Context,
    ) -> Iterable[ProducedEvent]: ...


ToolCallId = NewType("ToolCallId", str)
ToolResultId = NewType("ToolResultId", str)


@dataclass(frozen=True)
class ToolCall:
    id: ToolCallId
    name: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    id: ToolResultId
    tool_call: ToolCall
    result: Any
