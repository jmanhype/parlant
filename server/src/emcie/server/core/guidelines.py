from typing import NewType, Optional, Sequence
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

from emcie.server.base_models import DefaultBaseModel
from emcie.server.core.common import generate_id
from emcie.server.core.persistence.document_database import DocumentDatabase

GuidelineId = NewType("GuidelineId", str)


@dataclass(frozen=True)
class GuidelineData:
    predicate: str
    content: str


@dataclass(frozen=True)
class Guideline(GuidelineData):
    id: GuidelineId
    creation_utc: datetime

    def __str__(self) -> str:
        return f"When {self.predicate}, then {self.content}"


class GuidelineStore(ABC):
    @abstractmethod
    async def create_guideline(
        self,
        guideline_set: str,
        predicate: str,
        content: str,
        creation_utc: Optional[datetime] = None,
    ) -> Guideline: ...

    @abstractmethod
    async def list_guidelines(
        self,
        guideline_set: str,
    ) -> Sequence[Guideline]: ...

    @abstractmethod
    async def read_guideline(
        self,
        guideline_set: str,
        guideline_id: GuidelineId,
    ) -> Guideline: ...

    @abstractmethod
    async def delete_guideline(
        self,
        guideline_set: str,
        guideline_id: GuidelineId,
    ) -> None: ...


class GuidelineDocumentStore(GuidelineStore):
    class GuidelineDocument(DefaultBaseModel):
        id: GuidelineId
        guideline_set: str
        predicate: str
        content: str
        creation_utc: Optional[datetime] = None

    def __init__(self, database: DocumentDatabase):
        self._collection = database.get_or_create_collection(
            name="guidelines",
            schema=self.GuidelineDocument,
        )

    async def create_guideline(
        self,
        guideline_set: str,
        predicate: str,
        content: str,
        creation_utc: Optional[datetime] = None,
    ) -> Guideline:
        creation_utc = creation_utc or datetime.now(timezone.utc)

        guideline_id = await self._collection.insert_one(
            document={
                "id": generate_id(),
                "guideline_set": guideline_set,
                "predicate": predicate,
                "content": content,
                "creation_utc": creation_utc,
            },
        )

        return Guideline(
            id=GuidelineId(guideline_id),
            predicate=predicate,
            content=content,
            creation_utc=creation_utc,
        )

    async def list_guidelines(
        self,
        guideline_set: str,
    ) -> Sequence[Guideline]:
        return [
            Guideline(
                id=GuidelineId(d["id"]),
                predicate=d["predicate"],
                content=d["content"],
                creation_utc=d["creation_utc"],
            )
            for d in await self._collection.find(filters={"guideline_set": {"$eq": guideline_set}})
        ]

    async def read_guideline(
        self,
        guideline_set: str,
        guideline_id: GuidelineId,
    ) -> Guideline:
        guideline_document = await self._collection.find_one(
            filters={
                "guideline_set": {"$eq": guideline_set},
                "id": {"$eq": guideline_id},
            }
        )

        return Guideline(
            id=GuidelineId(guideline_document["id"]),
            predicate=guideline_document["predicate"],
            content=guideline_document["content"],
            creation_utc=guideline_document["creation_utc"],
        )

    async def delete_guideline(
        self,
        guideline_set: str,
        guideline_id: GuidelineId,
    ) -> None:
        await self._collection.delete_one(
            filters={
                "guideline_set": {"$eq": guideline_set},
                "id": {"$eq": guideline_id},
            }
        )
