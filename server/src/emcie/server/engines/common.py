from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterable

from emcie.server.agents import AgentId
from emcie.server.sessions import EventSource, SessionId


@dataclass(frozen=True)
class Context:
    session_id: SessionId
    agent_id: AgentId


@dataclass(frozen=True)
class GeneratedEvent:
    source: EventSource
    type: str
    data: dict[str, Any]


class Engine(ABC):
    @abstractmethod
    async def process(
        self,
        context: Context,
    ) -> Iterable[GeneratedEvent]: ...
