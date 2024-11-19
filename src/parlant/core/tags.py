from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import NewType, Optional, Sequence, TypedDict

from parlant.core.common import ItemNotFoundError, generate_id, UniqueId
from parlant.core.persistence.document_database import DocumentDatabase, ObjectId
from parlant.core.common import Version

TagId = NewType("TagId", str)


@dataclass(frozen=True)
class Tag:
    id: TagId
    creation_utc: datetime
    label: str


class TagUpdateParams(TypedDict, total=False):
    label: str


class TagStore(ABC):
    @abstractmethod
    async def create_tag(
        self,
        label: str,
        creation_utc: Optional[datetime] = None,
    ) -> Tag: ...

    @abstractmethod
    async def read_tag(
        self,
        tag_id: TagId,
    ) -> Tag: ...

    @abstractmethod
    async def update_tag(
        self,
        tag_id: TagId,
        params: TagUpdateParams,
    ) -> Tag: ...

    @abstractmethod
    async def list_tags(
        self,
    ) -> Sequence[Tag]: ...

    @abstractmethod
    async def delete_tag(
        self,
        tag_id: TagId,
    ) -> None: ...


class _TagDocument(TypedDict, total=False):
    id: ObjectId
    version: Version.String
    creation_utc: str
    label: str


class TagDocumentStore(TagStore):
    VERSION = Version.from_string("0.1.0")

    def __init__(self, database: DocumentDatabase) -> None:
        self._collection = database.get_or_create_collection(
            name="tags",
            schema=_TagDocument,
        )

    def _serialize(
        self,
        tag: Tag,
    ) -> _TagDocument:
        return _TagDocument(
            id=ObjectId(tag.id),
            version=self.VERSION.to_string(),
            creation_utc=tag.creation_utc.isoformat(),
            label=tag.label,
        )

    def _deserialize(self, document: _TagDocument) -> Tag:
        return Tag(
            id=TagId(document["id"]),
            creation_utc=datetime.fromisoformat(document["creation_utc"]),
            label=document["label"],
        )

    async def create_tag(
        self,
        label: str,
        creation_utc: Optional[datetime] = None,
    ) -> Tag:
        creation_utc = creation_utc or datetime.now(timezone.utc)

        tag = Tag(id=TagId(generate_id()), creation_utc=creation_utc, label=label)
        await self._collection.insert_one(self._serialize(tag))

        return tag

    async def read_tag(
        self,
        tag_id: TagId,
    ) -> Tag:
        document = await self._collection.find_one({"id": {"$eq": tag_id}})

        if not document:
            raise ItemNotFoundError(item_id=UniqueId(tag_id))

        return self._deserialize(document)

    async def update_tag(
        self,
        tag_id: TagId,
        params: TagUpdateParams,
    ) -> Tag:
        tag_document = await self._collection.find_one(filters={"id": {"$eq": tag_id}})

        if not tag_document:
            raise ItemNotFoundError(item_id=UniqueId(tag_id))

        result = await self._collection.update_one(
            filters={"id": {"$eq": tag_id}},
            params={"label": params["label"]},
        )

        assert result.updated_document

        return self._deserialize(document=result.updated_document)

    async def list_tags(
        self,
    ) -> Sequence[Tag]:
        return [self._deserialize(doc) for doc in await self._collection.find({})]

    async def delete_tag(
        self,
        tag_id: TagId,
    ) -> None:
        result = await self._collection.delete_one({"id": {"$eq": tag_id}})

        if result.deleted_count == 0:
            raise ItemNotFoundError(item_id=UniqueId(tag_id))
