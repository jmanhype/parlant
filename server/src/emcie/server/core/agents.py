from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import NewType, Optional, Sequence, TypedDict

from emcie.server.core.common import ItemNotFoundError, UniqueId, generate_id
from emcie.server.core.persistence.common import ObjectId
from emcie.server.core.persistence.document_database import (
    DocumentDatabase,
)

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
    async def list_agents(self) -> Sequence[Agent]: ...

    @abstractmethod
    async def read_agent(self, agent_id: AgentId) -> Agent: ...


class AgentDocument(TypedDict, total=False):
    id: ObjectId
    creation_utc: str
    name: str
    description: Optional[str]


def _serialize_agent(agent: Agent) -> AgentDocument:
    return AgentDocument(
        id=ObjectId(agent.id),
        creation_utc=agent.creation_utc.isoformat(),
        name=agent.name,
        description=agent.description,
    )


def _deserialize_agent_documet(agent_document: AgentDocument) -> Agent:
    return Agent(
        id=AgentId(agent_document["id"]),
        creation_utc=datetime.fromisoformat(agent_document["creation_utc"]),
        name=agent_document["name"],
        description=agent_document["description"],
    )


class AgentDocumentStore(AgentStore):
    def __init__(
        self,
        database: DocumentDatabase,
    ):
        self._collection = database.get_or_create_collection(
            name="agents",
            schema=AgentDocument,
        )

    async def create_agent(
        self,
        name: str,
        description: Optional[str] = None,
        creation_utc: Optional[datetime] = None,
    ) -> Agent:
        creation_utc = creation_utc or datetime.now(timezone.utc)

        agent = Agent(
            id=AgentId(generate_id()),
            name=name,
            description=description,
            creation_utc=creation_utc,
        )

        await self._collection.insert_one(document=_serialize_agent(agent=agent))

        return agent

    async def list_agents(
        self,
    ) -> Sequence[Agent]:
        return [_deserialize_agent_documet(d) for d in await self._collection.find(filters={})]

    async def read_agent(self, agent_id: AgentId) -> Agent:
        agent_document = await self._collection.find_one(
            filters={
                "id": {"$eq": agent_id},
            }
        )

        if not agent_document:
            raise ItemNotFoundError(item_id=UniqueId(agent_id))

        return _deserialize_agent_documet(agent_document)
