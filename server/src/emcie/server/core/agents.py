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
    description: Optional[str]
    creation_utc: datetime


class AgentStore(ABC):
    @abstractmethod
    async def create_agent(
        self,
        name: str,
        description: Optional[str] = None,
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
        description: Optional[str] = None,
        creation_utc: Optional[datetime] = None,
    ) -> Agent:
        creation_utc = creation_utc or datetime.now(timezone.utc)
        agent_document = await self._database.insert_one(
            self._collection_name,
            {
                "id": common.generate_id(),
                "name": name,
                "description": description,
                "creation_utc": creation_utc,
            },
        )
        return Agent(
            id=AgentId(agent_document["id"]),
            name=name,
            description=description,
            creation_utc=creation_utc,
        )

    async def list_agents(
        self,
    ) -> Iterable[Agent]:
        return (
            Agent(
                id=a["id"],
                name=a["name"],
                description=a.get("description"),
                creation_utc=a["creation_utc"],
            )
            for a in await self._database.find(self._collection_name, filters={})
        )

    async def read_agent(
        self,
        agent_id: AgentId,
    ) -> Agent:
        filters = {
            "id": FieldFilter(equal_to=agent_id),
        }
        agent_document = await self._database.find_one(self._collection_name, filters)
        return Agent(
            id=agent_document["id"],
            name=agent_document["name"],
            description=agent_document["description"],
            creation_utc=agent_document["creation_utc"],
        )
