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

from __future__ import annotations
from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass
from typing import (
    Awaitable,
    Callable,
    Generic,
    Optional,
    Sequence,
    TypeVar,
    TypedDict,
    cast,
)

from parlant.core.persistence.common import ObjectId, Where
from parlant.core.common import Version, generate_id


class BaseDocument(TypedDict, total=False):
    id: ObjectId
    version: Version.String


TDocument = TypeVar("TDocument", bound=BaseDocument)


class _MetadataDocument(TypedDict, total=False):
    id: ObjectId
    version: Version.String


async def check_migration_required(
    database: DocumentDatabase, store_version: Version.String
) -> bool:
    """
    Helper function to check if migration is required by comparing the version in metadata
    with the current store version.
    In case metadata is not found, it is created with the given store version.
    """
    lock = asyncio.Lock()

    metadata_collection = await database.get_or_create_collection(
        "metadata",
        _MetadataDocument,
        identity_loader,
    )

    async with lock:
        if metadata := await metadata_collection.find_one({}):
            return metadata["version"] != store_version
        else:
            await metadata_collection.insert_one(
                {
                    "id": ObjectId(generate_id()),
                    "version": store_version,
                }
            )
            return False  # No migration is required for a new store


async def update_metadata_version(
    database: DocumentDatabase, store_version: Version.String
) -> None:
    """
    Helper function to update the version in metadata for all documents in the database.
    """
    metadata_collection = await database.get_or_create_collection(
        "metadata",
        _MetadataDocument,
        identity_loader,
    )

    for doc in await metadata_collection.find({}):
        await metadata_collection.update_one(
            filters={"id": {"$eq": doc["id"]}},
            params={"version": store_version},
        )


@dataclass
class MigrationContext:
    """
    Context class to help with managing migrations across different versions.
    """

    from_version: Version
    to_version: Version
    collection: DocumentCollection
    metadata_collection: DocumentCollection


@dataclass(frozen=True)
class InsertResult:
    acknowledged: bool


@dataclass(frozen=True)
class UpdateResult(Generic[TDocument]):
    acknowledged: bool
    matched_count: int
    modified_count: int
    updated_document: Optional[TDocument]


@dataclass(frozen=True)
class DeleteResult(Generic[TDocument]):
    acknowledged: bool
    deleted_count: int
    deleted_document: Optional[TDocument]


async def identity_loader(doc: BaseDocument) -> TDocument:
    return cast(TDocument, doc)


class DocumentDatabase(ABC):
    @abstractmethod
    async def create_collection(
        self,
        name: str,
        schema: type[TDocument],
    ) -> DocumentCollection[TDocument]:
        """
        Creates a new collection with the given name and returns the collection.
        """
        ...

    @abstractmethod
    async def get_collection(
        self,
        name: str,
        schema: type[TDocument],
        document_loader: Callable[[BaseDocument], Awaitable[Optional[TDocument]]],
    ) -> DocumentCollection[TDocument]:
        """
        Retrieves an existing collection by its name.
        """
        ...

    @abstractmethod
    async def get_or_create_collection(
        self,
        name: str,
        schema: type[TDocument],
        document_loader: Callable[[BaseDocument], Awaitable[Optional[TDocument]]],
    ) -> DocumentCollection[TDocument]:
        """
        Retrieves an existing collection by its name or creates a new one if it does not exist.
        """
        ...

    @abstractmethod
    async def delete_collection(
        self,
        name: str,
    ) -> None:
        """
        Deletes a collection by its name.
        """
        ...


class DocumentCollection(ABC, Generic[TDocument]):
    @abstractmethod
    async def find(
        self,
        filters: Where,
    ) -> Sequence[TDocument]:
        """Finds all documents that match the given filters."""
        ...

    @abstractmethod
    async def find_one(
        self,
        filters: Where,
    ) -> Optional[TDocument]:
        """Returns the first document that matches the query criteria."""
        ...

    @abstractmethod
    async def insert_one(
        self,
        document: TDocument,
    ) -> InsertResult:
        """Inserts a single document into the collection."""
        ...

    @abstractmethod
    async def update_one(
        self,
        filters: Where,
        params: TDocument,
        upsert: bool = False,
    ) -> UpdateResult[TDocument]:
        """Updates the first document that matches the query criteria. If upsert is True,
        inserts the document if it does not exist."""
        ...

    @abstractmethod
    async def delete_one(
        self,
        filters: Where,
    ) -> DeleteResult[TDocument]:
        """Deletes the first document that matches the query criteria."""
        ...
