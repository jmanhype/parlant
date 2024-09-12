from typing import NewType, Optional, Sequence
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

from emcie.server.core.common import ItemNotFoundError, UniqueId, generate_id
from emcie.server.core.persistence.common import BaseDocument, ObjectId
from emcie.server.core.persistence.document_database import (
    DocumentDatabase,
)

GuidelineId = NewType("GuidelineId", str)


@dataclass(frozen=True)
class GuidelineContent:
    predicate: str
    action: str


@dataclass(frozen=True)
class Guideline:
    id: GuidelineId
    creation_utc: datetime
    content: GuidelineContent

    def __str__(self) -> str:
        return f"When {self.content.predicate}, then {self.content.action}"


class GuidelineStore(ABC):
    @abstractmethod
    async def create_guideline(
        self,
        guideline_set: str,
        predicate: str,
        action: str,
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
    ) -> Guideline: ...


class GuidelineDocumentStore(GuidelineStore):
    class GuidelineDocument(BaseDocument):
        creation_utc: datetime
        guideline_set: str
        predicate: str
        action: str

    def __init__(self, database: DocumentDatabase):
        self._collection = database.get_or_create_collection(
            name="guidelines",
            schema=self.GuidelineDocument,
        )

    async def create_guideline(
        self,
        guideline_set: str,
        predicate: str,
        action: str,
        creation_utc: Optional[datetime] = None,
    ) -> Guideline:
        creation_utc = creation_utc or datetime.now(timezone.utc)

        result = await self._collection.insert_one(
            document=self.GuidelineDocument(
                id=ObjectId(generate_id()),
                creation_utc=creation_utc,
                guideline_set=guideline_set,
                predicate=predicate,
                action=action,
            ),
        )

        return Guideline(
            id=GuidelineId(result.inserted_id),
            creation_utc=creation_utc,
            content=GuidelineContent(
                predicate=predicate,
                action=action,
            ),
        )

    async def list_guidelines(
        self,
        guideline_set: str,
    ) -> Sequence[Guideline]:
        return [
            Guideline(
                id=GuidelineId(d.id),
                creation_utc=d.creation_utc,
                content=GuidelineContent(
                    predicate=d.predicate,
                    action=d.action,
                ),
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

        if not guideline_document:
            raise ItemNotFoundError(
                item_id=UniqueId(guideline_id), message=f"with guideline_set '{guideline_set}'"
            )

        return Guideline(
            id=GuidelineId(guideline_document.id),
            creation_utc=guideline_document.creation_utc,
            content=GuidelineContent(
                predicate=guideline_document.predicate,
                action=guideline_document.action,
            ),
        )

    async def delete_guideline(
        self,
        guideline_set: str,
        guideline_id: GuidelineId,
    ) -> Guideline:
        result = await self._collection.delete_one(
            filters={
                "guideline_set": {"$eq": guideline_set},
                "id": {"$eq": guideline_id},
            }
        )

        if not result.deleted_document:
            raise ItemNotFoundError(
                item_id=UniqueId(guideline_id), message=f"with guideline_set '{guideline_set}'"
            )

        return Guideline(
            id=GuidelineId(result.deleted_document.id),
            creation_utc=result.deleted_document.creation_utc,
            content=GuidelineContent(
                predicate=result.deleted_document.predicate,
                action=result.deleted_document.action,
            ),
        )
