from abc import ABC, abstractmethod
from dataclasses import dataclass

from parlant.core.agents import AgentId
from parlant.core.sessions import SessionId
from parlant.core.emissions import EventEmitter


@dataclass(frozen=True)
class Context:
    session_id: SessionId
    agent_id: AgentId


class Engine(ABC):
    @abstractmethod
    async def process(
        self,
        context: Context,
        event_emitter: EventEmitter,
    ) -> bool: ...
