from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, NewType, Optional

from emcie.server.core import common

AgentId = NewType("AgentId", str)


@dataclass(frozen=True)
class Agent:
    id: AgentId
    creation_utc: datetime


class AgentStore:
    def __init__(
        self,
    ) -> None:
        self._agents: Dict[AgentId, Agent] = {}

    async def create_agent(
        self,
        creation_utc: Optional[datetime] = None,
    ) -> Agent:
        agent = Agent(
            id=AgentId(common.generate_id()),
            creation_utc=creation_utc or datetime.now(timezone.utc),
        )

        self._agents[agent.id] = agent

        return agent

    async def list_agents(self) -> Iterable[Agent]:
        return self._agents.values()

    async def read_agent(self, agent_id: AgentId) -> Agent:
        return self._agents[agent_id]
