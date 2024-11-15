from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import NewType, Optional, Sequence, TypedDict

from parlant.core.common import ItemNotFoundError, UniqueId, Version, generate_id
from parlant.core.persistence.document_database import (
    DocumentDatabase,
    ObjectId,
)

EndUserId = NewType("EndUserId", str)
EndUserTagId = NewType("EndUserTagId", str)
EndUserTagAssociationId = NewType("EndUserTagAssociationId", str)


@dataclass(frozen=True)
class EndUserTag:
    id: EndUserTagId
    label: str
    creation_utc: datetime


@dataclass(frozen=True)
class EndUserTagAssociation:
    id: EndUserTagAssociationId
    creation_utc: datetime
    tag_id: EndUserTagId
    end_user_id: EndUserId


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

    @abstractmethod
    async def set_tag(
        self,
        label: str,
        end_user_id: EndUserId,
        creation_utc: Optional[datetime] = None,
    ) -> EndUserTag: ...

    @abstractmethod
    async def get_tags(
        self,
        end_user_id: EndUserId,
    ) -> Sequence[EndUserTag]: ...

    @abstractmethod
    async def delete_tag(
        self,
        tag_id: EndUserTagId,
        end_user_id: EndUserId,
    ) -> None: ...

    @abstractmethod
    async def list_tags(
        self,
    ) -> Sequence[EndUserTag]: ...


class _EndUserDocument(TypedDict, total=False):
    id: ObjectId
    version: Version.String
    creation_utc: str
    name: str
    email: str


class _EndUserTagDocument(TypedDict, total=False):
    id: ObjectId
    version: Version.String
    creation_utc: str
    label: str


class _EndUserTagAssociationDocument(TypedDict, total=False):
    id: ObjectId
    version: Version.String
    creation_utc: str
    tag_id: EndUserTagId
    end_user_id: EndUserId


class EndUserDocumentStore(EndUserStore):
    VERSION = Version.from_string("0.1.0")

    def __init__(
        self,
        database: DocumentDatabase,
    ) -> None:
        self._end_users_collection = database.get_or_create_collection(
            name="end_users",
            schema=_EndUserDocument,
        )
        self._tags_collection = database.get_or_create_collection(
            name="tags",
            schema=_EndUserTagDocument,
        )
        self._user_tag_assocication_collection = database.get_or_create_collection(
            name="user_tag_association",
            schema=_EndUserTagAssociationDocument,
        )

    def _serialize_end_user(self, end_user: EndUser) -> _EndUserDocument:
        return _EndUserDocument(
            id=ObjectId(end_user.id),
            version=self.VERSION.to_string(),
            creation_utc=end_user.creation_utc.isoformat(),
            name=end_user.name,
            email=end_user.email,
        )

    def _deserialize_end_user(self, end_user_document: _EndUserDocument) -> EndUser:
        return EndUser(
            id=EndUserId(end_user_document["id"]),
            creation_utc=datetime.fromisoformat(end_user_document["creation_utc"]),
            name=end_user_document["name"],
            email=end_user_document["email"],
        )

    def _serialize_tag(self, tag: EndUserTag) -> _EndUserTagDocument:
        return _EndUserTagDocument(
            id=ObjectId(tag.id),
            version=self.VERSION.to_string(),
            creation_utc=tag.creation_utc.isoformat(),
            label=tag.label,
        )

    def _deserialize_tag(self, tag_document: _EndUserTagDocument) -> EndUserTag:
        return EndUserTag(
            id=EndUserTagId(tag_document["id"]),
            creation_utc=datetime.fromisoformat(tag_document["creation_utc"]),
            label=tag_document["label"],
        )

    def _serialize_association(
        self, association: EndUserTagAssociation
    ) -> _EndUserTagAssociationDocument:
        return _EndUserTagAssociationDocument(
            id=ObjectId(association.id),
            version=self.VERSION.to_string(),
            creation_utc=association.creation_utc.isoformat(),
            tag_id=association.tag_id,
            end_user_id=association.end_user_id,
        )

    def _deserialize_association(
        self, association_document: _EndUserTagAssociationDocument
    ) -> EndUserTagAssociation:
        return EndUserTagAssociation(
            id=EndUserTagAssociationId(association_document["id"]),
            creation_utc=datetime.fromisoformat(association_document["creation_utc"]),
            tag_id=association_document["tag_id"],
            end_user_id=association_document["end_user_id"],
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

        await self._end_users_collection.insert_one(
            document=self._serialize_end_user(end_user=end_user)
        )

        return end_user

    async def read_end_user(
        self,
        end_user_id: EndUserId,
    ) -> EndUser:
        end_user_document = await self._end_users_collection.find_one(
            filters={"id": {"$eq": end_user_id}}
        )

        if not end_user_document:
            raise ItemNotFoundError(item_id=UniqueId(end_user_id))

        return self._deserialize_end_user(end_user_document)

    async def set_tag(
        self,
        label: str,
        end_user_id: EndUserId,
        creation_utc: Optional[datetime] = None,
    ) -> EndUserTag:
        _ = await self.read_end_user(end_user_id)

        creation_utc = creation_utc or datetime.now(timezone.utc)

        result = await self._tags_collection.update_one(
            filters={"label": {"$eq": label}},
            params=self._serialize_tag(
                EndUserTag(
                    id=EndUserTagId(generate_id()),
                    creation_utc=creation_utc,
                    label=label,
                )
            ),
            upsert=True,
        )

        assert result.updated_document

        tag = self._deserialize_tag(result.updated_document)

        association = EndUserTagAssociation(
            id=EndUserTagAssociationId(generate_id()),
            creation_utc=creation_utc,
            tag_id=tag.id,
            end_user_id=end_user_id,
        )

        _ = await self._user_tag_assocication_collection.insert_one(
            document=self._serialize_association(association)
        )

        return tag

    async def get_tags(
        self,
        end_user_id: EndUserId,
    ) -> Sequence[EndUserTag]:
        _ = await self.read_end_user(end_user_id)

        associations = await self._user_tag_assocication_collection.find(
            filters={"end_user_id": {"$eq": end_user_id}}
        )

        return [
            self._deserialize_tag(d)
            for d in await self._tags_collection.find(
                filters={
                    "$or": [
                        {"id": {"$eq": tag_id}}
                        for tag_id in map(lambda a: a["tag_id"], associations)
                    ]
                }
            )
        ]

    async def delete_tag(
        self,
        tag_id: EndUserTagId,
        end_user_id: EndUserId,
    ) -> None:
        await self._user_tag_assocication_collection.delete_one(
            filters={
                "end_user_id": {"$eq": end_user_id},
                "tag_id": {"$eq": tag_id},
            }
        )

    async def list_tags(
        self,
    ) -> Sequence[EndUserTag]:
        return [self._deserialize_tag(t) for t in await self._tags_collection.find(filters={})]
