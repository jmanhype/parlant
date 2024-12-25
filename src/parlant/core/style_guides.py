# Copyright 2024 Emcie Co Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import NewType, Optional, Sequence
from typing_extensions import override, TypedDict, Self
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

from parlant.core.async_utils import ReaderWriterLock
from parlant.core.common import ItemNotFoundError, UniqueId, Version, generate_id
from parlant.core.sessions import EventSource
from parlant.core.persistence.common import ObjectId
from parlant.core.persistence.document_database import DocumentDatabase, DocumentCollection

StyleGuideId = NewType("StyleGuideId", str)


@dataclass(frozen=True)
class StyleGuideEvent:
    source: EventSource
    message: str


@dataclass(frozen=True)
class StyleGuideExample:
    before: Sequence[StyleGuideEvent]
    after: Sequence[StyleGuideEvent]
    violation: str


@dataclass(frozen=True)
class StyleGuideContent:
    principle: str
    examples: Sequence[StyleGuideExample]


@dataclass(frozen=True)
class StyleGuide:
    id: StyleGuideId
    creation_utc: datetime
    content: StyleGuideContent


class StyleGuideUpdateParams(TypedDict, total=False):
    principle: str
    examples: Sequence[StyleGuideExample]


class _StyleGuideEventDocument(TypedDict):
    source: EventSource
    message: str


class _StyleGuideExampleDocument(TypedDict):
    before: Sequence[_StyleGuideEventDocument]
    after: Sequence[_StyleGuideEventDocument]
    violation: str


class _StyleGuideDocument(TypedDict, total=False):
    id: ObjectId
    version: Version.String
    creation_utc: str
    style_guide_set: str
    principle: str
    examples: Sequence[_StyleGuideExampleDocument]


class StyleGuideStore(ABC):
    @abstractmethod
    async def create_style_guide(
        self,
        style_guide_set: str,
        principle: str,
        examples: Sequence[StyleGuideExample],
        creation_utc: Optional[datetime] = None,
    ) -> StyleGuide: ...

    @abstractmethod
    async def read_style_guide(
        self, style_guide_set: str, style_guide_id: StyleGuideId
    ) -> StyleGuide: ...

    @abstractmethod
    async def list_style_guides(
        self,
        style_guide_set: str,
    ) -> Sequence[StyleGuide]: ...

    @abstractmethod
    async def update_style_guide(
        self,
        style_guide_set: str,
        style_guide_id: StyleGuideId,
        params: StyleGuideUpdateParams,
    ) -> StyleGuide: ...

    @abstractmethod
    async def delete_style_guide(
        self, style_guide_set: str, style_guide_id: StyleGuideId
    ) -> None: ...


class StyleGuideDocumentStore(StyleGuideStore):
    VERSION = Version.from_string("0.1.0")

    def __init__(self, database: DocumentDatabase):
        self._database = database
        self._collection: DocumentCollection[_StyleGuideDocument]

        self._lock = ReaderWriterLock()

    async def __aenter__(self) -> Self:
        self._collection = await self._database.get_or_create_collection(
            name="style_guides",
            schema=_StyleGuideDocument,
        )
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[object],
    ) -> None:
        pass

    def _serialize_event(self, event: StyleGuideEvent) -> _StyleGuideEventDocument:
        return _StyleGuideEventDocument(
            source=event.source,
            message=event.message,
        )

    def _deserialize_event(self, doc: _StyleGuideEventDocument) -> StyleGuideEvent:
        return StyleGuideEvent(source=doc["source"], message=doc["message"])

    def _serialize_example(self, example: StyleGuideExample) -> _StyleGuideExampleDocument:
        return _StyleGuideExampleDocument(
            before=[self._serialize_event(evt) for evt in example.before],
            after=[self._serialize_event(evt) for evt in example.after],
            violation=example.violation,
        )

    def _deserialize_example(self, doc: _StyleGuideExampleDocument) -> StyleGuideExample:
        return StyleGuideExample(
            before=[self._deserialize_event(evt_doc) for evt_doc in doc["before"]],
            after=[self._deserialize_event(evt_doc) for evt_doc in doc["after"]],
            violation=doc["violation"],
        )

    def _serialize(
        self,
        style_guide: StyleGuide,
        style_guide_set: str,
    ) -> _StyleGuideDocument:
        return _StyleGuideDocument(
            id=ObjectId(style_guide.id),
            version=self.VERSION.to_string(),
            creation_utc=style_guide.creation_utc.isoformat(),
            style_guide_set=style_guide_set,
            principle=style_guide.content.principle,
            examples=[self._serialize_example(ex) for ex in style_guide.content.examples],
        )

    def _deserialize(
        self,
        doc: _StyleGuideDocument,
    ) -> StyleGuide:
        return StyleGuide(
            id=StyleGuideId(doc["id"]),
            creation_utc=datetime.fromisoformat(doc["creation_utc"]),
            content=StyleGuideContent(
                principle=doc["principle"],
                examples=[self._deserialize_example(ex) for ex in doc["examples"]],
            ),
        )

    @override
    async def create_style_guide(
        self,
        style_guide_set: str,
        principle: str,
        examples: Sequence[StyleGuideExample],
        creation_utc: Optional[datetime] = None,
    ) -> StyleGuide:
        async with self._lock.writer_lock:
            creation_utc = creation_utc or datetime.now(timezone.utc)

            style_guide = StyleGuide(
                id=StyleGuideId(generate_id()),
                creation_utc=creation_utc,
                content=StyleGuideContent(
                    principle=principle,
                    examples=examples,
                ),
            )

            await self._collection.insert_one(
                document=self._serialize(style_guide, style_guide_set)
            )

            return style_guide

    @override
    async def list_style_guides(
        self,
        style_guide_set: str,
    ) -> Sequence[StyleGuide]:
        async with self._lock.reader_lock:
            docs = await self._collection.find(
                filters={"style_guide_set": {"$eq": style_guide_set}}
            )

            return [self._deserialize(d) for d in docs]

    @override
    async def read_style_guide(
        self, style_guide_set: str, style_guide_id: StyleGuideId
    ) -> StyleGuide:
        async with self._lock.reader_lock:
            doc = await self._collection.find_one(
                filters={
                    "style_guide_set": {"$eq": style_guide_set},
                    "id": {"$eq": style_guide_id},
                }
            )

        if not doc:
            raise ItemNotFoundError(
                item_id=UniqueId(style_guide_id),
                message=f"with style_guide_set  {style_guide_set}",
            )

        return self._deserialize(doc)

    @override
    async def delete_style_guide(self, style_guide_set: str, style_guide_id: StyleGuideId) -> None:
        async with self._lock.writer_lock:
            result = await self._collection.delete_one(filters={"id": {"$eq": style_guide_id}})

        if not result.deleted_document:
            raise ItemNotFoundError(
                item_id=UniqueId(style_guide_id),
                message=f"with style_guide_set  {style_guide_set}",
            )

    @override
    async def update_style_guide(
        self,
        style_guide_set: str,
        style_guide_id: StyleGuideId,
        params: StyleGuideUpdateParams,
    ) -> StyleGuide:
        async with self._lock.writer_lock:
            update_doc: _StyleGuideDocument = {}
            if "principle" in params:
                update_doc["principle"] = params["principle"]
            if "examples" in params:
                update_doc["examples"] = [self._serialize_example(ex) for ex in params["examples"]]

            result = await self._collection.update_one(
                filters={
                    "style_guide_set": {"$eq": style_guide_set},
                    "id": {"$eq": style_guide_id},
                },
                params=update_doc,
            )

        if not result.updated_document:
            raise ItemNotFoundError(
                item_id=UniqueId(style_guide_id),
                message=f"with style_guide_set  {style_guide_set}",
            )

        return self._deserialize(result.updated_document)
