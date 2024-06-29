from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, NewType, Optional

from emcie.server.core import common
from emcie.server.core.persistence import DocumentDatabase

AgentId = NewType("AgentId", str)


@dataclass(frozen=True)
class Agent:
    id: AgentId
    name: str
    creation_utc: datetime


class AgentStore(ABC):
    @abstractmethod
    async def create_agent(
        self,
        creation_utc: Optional[datetime] = None,
    ) -> Agent:
        pass

    @abstractmethod
    async def list_agents(self) -> Iterable[Agent]:
        pass

    @abstractmethod
    async def read_agent(self, agent_id: AgentId) -> Agent:
        pass


class AgentDocumentStore(AgentStore):
    def __init__(self, database: DocumentDatabase[Agent]):
        self.database = database

    async def create_agent(
        self,
        name: str,
        creation_utc: Optional[datetime] = None,
    ) -> Agent:
        agent = Agent(
            id=AgentId(common.generate_id()),
            name=name,
            creation_utc=creation_utc or datetime.now(timezone.utc),
        )
        await self.database.add_document("agents", agent.id, agent)
        return agent

    async def list_agents(self) -> Iterable[Agent]:
        return await self.database.read_documents("agents")

    async def read_agent(self, agent_id: AgentId) -> Agent:
        return await self.database.read_document("agents", agent_id)
