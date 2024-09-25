from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import NewType, Optional, TypedDict

from emcie.server.core.common import ItemNotFoundError, UniqueId, generate_id
from emcie.server.core.persistence.common import ObjectId
from emcie.server.core.persistence.document_database import (
    DocumentDatabase,
)

EndUserId = NewType("EndUserId", str)


@dataclass(frozen=True)
class EndUser:
    id: EndUserId
    creation_utc: datetime
    name: str
    email: str


class EndUserStore(ABC):
    @abstractmethod
    async def create_end_user(
        self,
        name: str,
        email: str,
        creation_utc: Optional[datetime] = None,
    ) -> EndUser: ...

    @abstractmethod
    async def read_end_user(
        self,
        end_user_id: EndUserId,
    ) -> EndUser: ...


class EndUserDocument(TypedDict, total=False):
    id: ObjectId
    creation_utc: str
    name: str
    email: str


class EndUserDocumentStore(EndUserStore):
    def __init__(
        self,
        database: DocumentDatabase,
    ) -> None:
        self._collection = database.get_or_create_collection(
            name="end_users",
            schema=EndUserDocument,
        )

    def _serialize_end_user(self, end_user: EndUser) -> EndUserDocument:
        return EndUserDocument(
            id=ObjectId(end_user.id),
            creation_utc=end_user.creation_utc.isoformat(),
            name=end_user.name,
            email=end_user.email,
        )

    def _deserialize_end_user_documet(self, end_user_document: EndUserDocument) -> EndUser:
        return EndUser(
            id=EndUserId(end_user_document["id"]),
            creation_utc=datetime.fromisoformat(end_user_document["creation_utc"]),
            name=end_user_document["name"],
            email=end_user_document["email"],
        )

    async def create_end_user(
        self,
        name: str,
        email: str,
        creation_utc: Optional[datetime] = None,
    ) -> EndUser:
        creation_utc = creation_utc or datetime.now(timezone.utc)

        end_user = EndUser(
            id=EndUserId(generate_id()),
            name=name,
            email=email,
            creation_utc=creation_utc,
        )

        await self._collection.insert_one(document=self._serialize_end_user(end_user=end_user))

        return end_user

    async def read_end_user(
        self,
        end_user_id: EndUserId,
    ) -> EndUser:
        end_user_document = await self._collection.find_one(filters={"id": {"$eq": end_user_id}})

        if not end_user_document:
            raise ItemNotFoundError(item_id=UniqueId(end_user_id))

        return self._deserialize_end_user_documet(end_user_document)
