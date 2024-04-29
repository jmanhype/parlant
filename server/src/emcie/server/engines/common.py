from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

from emcie.server.agents import AgentId
from emcie.server.sessions import Event, SessionId


@dataclass(frozen=True)
class Context:
    session_id: SessionId
    agent_id: AgentId


class Engine(ABC):
    @abstractmethod
    async def process(self, context: Context) -> List[Event]: ...
