from abc import ABC, abstractmethod
from dataclasses import dataclass

from parlant.server.core.agents import AgentId
from parlant.server.core.sessions import SessionId
from parlant.server.core.emissions import EventEmitter


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
