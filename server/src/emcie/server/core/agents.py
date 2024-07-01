from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, NewType, Optional

from emcie.server.core import common
from emcie.server.core.persistence import DocumentDatabase, FieldFilter

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
        name: str,
        creation_utc: Optional[datetime] = None,
    ) -> Agent: ...

    @abstractmethod
    async def list_agents(self) -> Iterable[Agent]: ...

    @abstractmethod
    async def read_agent(
        self,
        agent_id: AgentId,
    ) -> Agent: ...


class AgentDocumentStore(AgentStore):
    def __init__(
        self,
        database: DocumentDatabase,
    ):
        self._database = database
        self._collection_name = "agents"

    async def create_agent(
        self,
        name: str,
        creation_utc: Optional[datetime] = None,
    ) -> Agent:
        agent_to_insert = {
            "name": name,
            "creation_utc": creation_utc or datetime.now(timezone.utc),
        }
        agent = common.create_instance_from_dict(
            Agent,
            await self._database.insert_one(self._collection_name, agent_to_insert),
        )
        return agent

    async def list_agents(
        self,
    ) -> Iterable[Agent]:
        return (
            common.create_instance_from_dict(Agent, a)
            for a in await self._database.find(self._collection_name, filters={})
        )

    async def read_agent(
        self,
        agent_id: AgentId,
    ) -> Agent:
        filters = {
            "id": FieldFilter(equal_to=agent_id),
        }
        agent = common.create_instance_from_dict(
            Agent, await self._database.find_one(self._collection_name, filters)
        )
        return agent
