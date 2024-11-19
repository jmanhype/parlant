from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, NewType, Optional, Sequence, TypeAlias, TypedDict, Union

from parlant.core.tags import TagId
from parlant.core.common import ItemNotFoundError, UniqueId, Version, generate_id
from parlant.core.persistence.document_database import (
    DocumentDatabase,
    ObjectId,
)

EndUserId = NewType("EndUserId", str)

ExtraType: TypeAlias = Mapping[str, Union[str, int, float, bool]]


@dataclass(frozen=True)
class EndUser:
    id: EndUserId
    creation_utc: datetime
    name: str
    extra: ExtraType
    tags: Sequence[TagId]


class EndUserUpdateParams(TypedDict, total=False):
    name: str


class EndUserStore(ABC):
    @abstractmethod
    async def create_end_user(
        self,
        name: str,
        extra: ExtraType = {},
        creation_utc: Optional[datetime] = None,
    ) -> EndUser: ...

    @abstractmethod
    async def read_end_user(
        self,
        end_user_id: EndUserId,
    ) -> EndUser: ...

    @abstractmethod
    async def update_end_user(
        self,
        end_user_id: EndUserId,
        params: EndUserUpdateParams,
    ) -> EndUser: ...

    @abstractmethod
    async def list_end_users(self) -> Sequence[EndUser]: ...

    @abstractmethod
    async def add_tag(
        self,
        end_user_id: EndUserId,
        tag_id: TagId,
        creation_utc: Optional[datetime] = None,
    ) -> EndUser: ...

    @abstractmethod
    async def remove_tag(
        self,
        end_user_id: EndUserId,
        tag_id: TagId,
    ) -> EndUser: ...

    @abstractmethod
    async def add_extra(
        self,
        end_user_id: EndUserId,
        extra: ExtraType,
    ) -> EndUser: ...

    @abstractmethod
    async def remove_extra(
        self,
        end_user_id: EndUserId,
        keys: Sequence[str],
    ) -> EndUser: ...


class _EndUserDocument(TypedDict, total=False):
    id: ObjectId
    version: Version.String
    creation_utc: str
    name: str
    extra: ExtraType


class _EndUserTagAssociationDocument(TypedDict, total=False):
    id: ObjectId
    version: Version.String
    creation_utc: str
    end_user_id: EndUserId
    tag_id: TagId


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
        self._end_user_tag_association_collection = database.get_or_create_collection(
            name="end_user_tag_associations",
            schema=_EndUserTagAssociationDocument,
        )

    def _serialize_end_user(self, end_user: EndUser) -> _EndUserDocument:
        return _EndUserDocument(
            id=ObjectId(end_user.id),
            version=self.VERSION.to_string(),
            creation_utc=end_user.creation_utc.isoformat(),
            name=end_user.name,
            extra=end_user.extra,
        )

    async def _deserialize_end_user(self, end_user_document: _EndUserDocument) -> EndUser:
        tags = [
            doc["tag_id"]
            for doc in await self._end_user_tag_association_collection.find(
                {"end_user_id": {"$eq": end_user_document["id"]}}
            )
        ]

        return EndUser(
            id=EndUserId(end_user_document["id"]),
            creation_utc=datetime.fromisoformat(end_user_document["creation_utc"]),
            name=end_user_document["name"],
            extra=end_user_document["extra"],
            tags=tags,
        )

    async def create_end_user(
        self,
        name: str,
        extra: ExtraType = {},
        creation_utc: Optional[datetime] = None,
    ) -> EndUser:
        creation_utc = creation_utc or datetime.now(timezone.utc)

        end_user = EndUser(
            id=EndUserId(generate_id()),
            name=name,
            extra=extra,
            creation_utc=creation_utc,
            tags=[],
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

        return await self._deserialize_end_user(end_user_document)

    async def update_end_user(
        self,
        end_user_id: EndUserId,
        params: EndUserUpdateParams,
    ) -> EndUser:
        end_user_document = await self._end_users_collection.find_one(
            filters={"id": {"$eq": end_user_id}}
        )

        if not end_user_document:
            raise ItemNotFoundError(item_id=UniqueId(end_user_id))

        result = await self._end_users_collection.update_one(
            filters={"id": {"$eq": end_user_id}},
            params={"name": params["name"]},
        )

        assert result.updated_document

        return await self._deserialize_end_user(end_user_document=result.updated_document)

    async def list_end_users(self) -> Sequence[EndUser]:
        return [
            await self._deserialize_end_user(e) for e in await self._end_users_collection.find({})
        ]

    async def add_tag(
        self,
        end_user_id: EndUserId,
        tag_id: TagId,
        creation_utc: Optional[datetime] = None,
    ) -> EndUser:
        creation_utc = creation_utc or datetime.now(timezone.utc)

        association_document: _EndUserTagAssociationDocument = {
            "id": ObjectId(generate_id()),
            "version": self.VERSION.to_string(),
            "creation_utc": creation_utc.isoformat(),
            "end_user_id": end_user_id,
            "tag_id": tag_id,
        }

        _ = await self._end_user_tag_association_collection.insert_one(
            document=association_document
        )

        end_user_document = await self._end_users_collection.find_one({"id": {"$eq": end_user_id}})

        if not end_user_document:
            raise ItemNotFoundError(item_id=UniqueId(end_user_id))

        return await self._deserialize_end_user(end_user_document=end_user_document)

    async def remove_tag(
        self,
        end_user_id: EndUserId,
        tag_id: TagId,
    ) -> EndUser:
        delete_result = await self._end_user_tag_association_collection.delete_one(
            {
                "end_user_id": {"$eq": end_user_id},
                "tag_id": {"$eq": tag_id},
            }
        )

        if delete_result.deleted_count == 0:
            raise ItemNotFoundError(item_id=UniqueId(tag_id))

        end_user_document = await self._end_users_collection.find_one({"id": {"$eq": end_user_id}})

        if not end_user_document:
            raise ItemNotFoundError(item_id=UniqueId(end_user_id))

        return await self._deserialize_end_user(end_user_document=end_user_document)

    async def add_extra(
        self,
        end_user_id: EndUserId,
        extra: ExtraType,
    ) -> EndUser:
        end_user_document = await self._end_users_collection.find_one({"id": {"$eq": end_user_id}})

        if not end_user_document:
            raise ItemNotFoundError(item_id=UniqueId(end_user_id))

        updated_extra = {**end_user_document["extra"], **extra}

        result = await self._end_users_collection.update_one(
            filters={"id": {"$eq": end_user_id}},
            params={"extra": updated_extra},
        )

        assert result.updated_document

        return await self._deserialize_end_user(end_user_document=result.updated_document)

    async def remove_extra(
        self,
        end_user_id: EndUserId,
        keys: Sequence[str],
    ) -> EndUser:
        end_user_document = await self._end_users_collection.find_one({"id": {"$eq": end_user_id}})

        if not end_user_document:
            raise ItemNotFoundError(item_id=UniqueId(end_user_id))

        updated_extra = {k: v for k, v in end_user_document["extra"].items() if k not in keys}

        result = await self._end_users_collection.update_one(
            filters={"id": {"$eq": end_user_id}},
            params={"extra": updated_extra},
        )

        assert result.updated_document

        return await self._deserialize_end_user(end_user_document=result.updated_document)
