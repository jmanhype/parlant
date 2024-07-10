from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable

from emcie.server.core.agents import AgentId
from emcie.server.core.common import JSONSerializable
from emcie.server.core.sessions import EventSource, SessionId


@dataclass(frozen=True)
class Context:
    session_id: SessionId
    agent_id: AgentId


@dataclass(frozen=True)
class ProducedEvent:
    source: EventSource
    kind: str
    data: JSONSerializable


class Engine(ABC):
    @abstractmethod
    async def process(
        self,
        context: Context,
    ) -> Iterable[ProducedEvent]: ...
