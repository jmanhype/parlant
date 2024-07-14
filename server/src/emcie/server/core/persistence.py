from __future__ import annotations
from abc import ABC, abstractmethod
import asyncio
from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Callable, Iterable, Optional, Sequence, Type, TypedDict
import aiofiles

from emcie.server.base_models import DefaultBaseModel


class FieldFilter(TypedDict, total=False):
    equal_to: Any
    not_equal_to: Any
    greater_than: Any
    greater_than_or_equal_to: Any
    less_than: Any
    less_than_or_equal_to: Any
    regex: str


@dataclass(frozen=True)
class CollectionDescriptor:
    name: str
    schema: Type[DefaultBaseModel]


class DocumentDatabase(ABC):

    @abstractmethod
    async def insert_one(
        self,
        collection: CollectionDescriptor,
        document: dict[str, Any],
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def find(
        self,
        collection: CollectionDescriptor,
        filters: dict[str, FieldFilter],
    ) -> Sequence[dict[str, Any]]: ...

    @abstractmethod
    async def find_one(
        self,
        collection: CollectionDescriptor,
        filters: dict[str, FieldFilter],
    ) -> dict[str, Any]:
        """
        Returns the first document that matches the query criteria.
        """

    ...

    @abstractmethod
    async def update_one(
        self,
        collection: CollectionDescriptor,
        filters: dict[str, FieldFilter],
        updated_document: dict[str, Any],
        upsert: bool = False,
    ) -> dict[str, Any]:
        """
        Updates the first document that matches the query criteria.
        """
        ...

    @abstractmethod
    async def delete_one(
        self,
        collection: CollectionDescriptor,
        filters: dict[str, FieldFilter],
    ) -> None:
        """
        Deletes the first document that matches the query criteria.
        """
        ...

    async def flush(self) -> None: ...


def _matches_filters(
    field_filters: dict[str, FieldFilter],
    candidate: dict[str, Any],
) -> bool:
    tests: dict[str, Callable[[Any, Any], bool]] = {
        "equal_to": lambda candidate, filter_value: candidate == filter_value,
        "not_equal_to": lambda candidate, filter_value: candidate != filter_value,
        "greater_than": lambda candidate, filter_value: candidate > filter_value,
        "greater_than_or_equal_to": lambda candidate, filter_value: candidate >= filter_value,
        "less_than": lambda candidate, filter_value: candidate < filter_value,
        "less_than_or_equal_to": lambda candidate, filter_value: candidate <= filter_value,
        "regex": lambda candidate, filter_value: bool(re.match(str(filter_value), str(candidate))),
    }
    for field, field_filter in field_filters.items():
        for filter_name, filter_value in field_filter.items():
            if not tests[filter_name](candidate.get(field), filter_value):
                return False
    return True


class TransientDocumentDatabase(DocumentDatabase):
    def __init__(
        self,
        collections: Optional[dict[str, list[dict[str, Any]]]] = None,
    ) -> None:
        self._collections = collections if collections else defaultdict(list)
        self._collection_descriptors: dict[str, CollectionDescriptor] = {}

    async def insert_one(
        self,
        collection: CollectionDescriptor,
        document: dict[str, Any],
    ) -> dict[str, Any]:
        self._collection_descriptors[collection.name] = collection
        self._collections[collection.name].append(document)
        return document

    async def find(
        self,
        collection: CollectionDescriptor,
        filters: dict[str, FieldFilter],
    ) -> Sequence[dict[str, Any]]:
        self._collection_descriptors[collection.name] = collection
        return list(
            filter(
                lambda d: _matches_filters(filters, d),
                self._collections[collection.name],
            )
        )

    async def find_one(
        self,
        collection: CollectionDescriptor,
        filters: dict[str, FieldFilter],
    ) -> dict[str, Any]:
        self._collection_descriptors[collection.name] = collection
        matched_documents = await self.find(collection, filters)
        if len(matched_documents) >= 1:
            return matched_documents[0]
        raise ValueError("No document found matching the provided filters.")

    async def update_one(
        self,
        collection: CollectionDescriptor,
        filters: dict[str, FieldFilter],
        updated_document: dict[str, Any],
        upsert: bool = False,
    ) -> dict[str, Any]:
        self._collection_descriptors[collection.name] = collection
        for i, d in enumerate(self._collections[collection.name]):
            if _matches_filters(filters, d):
                self._collections[collection.name][i] = updated_document
                return updated_document
        if upsert:
            document = await self.insert_one(collection, updated_document)
            return document

        raise ValueError("No document found matching the provided filters.")

    async def delete_one(
        self,
        collection: CollectionDescriptor,
        filters: dict[str, FieldFilter],
    ) -> None:
        self._collection_descriptors[collection.name] = collection
        for i, d in enumerate(self._collections[collection.name]):
            if _matches_filters(filters, d):
                del self._collections[collection.name][i]
                return
        raise ValueError("No document found matching the provided filters.")

    async def list_collections(self) -> Iterable[str]:
        return self._collections.keys()

    async def get_collection(
        self,
        collection_name: str,
    ) -> CollectionDescriptor:
        return self._collection_descriptors[collection_name]


class JSONFileDocumentDatabase(DocumentDatabase):

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self._lock = asyncio.Lock()
        self.op_counter = 0
        if not self.file_path.exists():
            self.file_path.write_text(json.dumps({}))
        self.transient_db: TransientDocumentDatabase

    async def __aenter__(self) -> JSONFileDocumentDatabase:
        self.transient_db = TransientDocumentDatabase(await self._load_data())
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[object],
    ) -> bool:
        await self.flush()
        return False

    async def _process_operation_counter(self) -> None:
        self.op_counter += 1
        if self.op_counter % 5:
            await self.flush()

    async def _load_data(
        self,
    ) -> dict[str, list[dict[str, Any]]]:
        async with self._lock:
            # Return an empty JSON object if the file is empty
            if self.file_path.stat().st_size == 0:
                return {}

            async with aiofiles.open(self.file_path, "r") as file:
                data: dict[str, Any] = json.loads(await file.read())
                return data

    async def _save_data(
        self,
        data: dict[str, list[dict[str, Any]]],
    ) -> None:
        async with self._lock:
            async with aiofiles.open(self.file_path, mode="w") as file:
                json_string = json.dumps(
                    data,
                    ensure_ascii=False,
                    indent=4,
                )
                await file.write(json_string)

    async def insert_one(
        self,
        collection: CollectionDescriptor,
        document: dict[str, Any],
    ) -> dict[str, Any]:
        result = await self.transient_db.insert_one(
            collection,
            collection.schema(**document).model_dump(mode="json"),
        )
        await self._process_operation_counter()
        return collection.schema.model_validate(result).model_dump()

    async def find(
        self,
        collection: CollectionDescriptor,
        filters: dict[str, FieldFilter],
    ) -> Sequence[dict[str, Any]]:
        return [
            collection.schema.model_validate(doc).model_dump()
            for doc in await self.transient_db.find(collection, filters)
        ]

    async def find_one(
        self,
        collection: CollectionDescriptor,
        filters: dict[str, FieldFilter],
    ) -> dict[str, Any]:
        result = await self.transient_db.find_one(collection, filters)
        return collection.schema.model_validate(result).model_dump()

    async def update_one(
        self,
        collection: CollectionDescriptor,
        filters: dict[str, FieldFilter],
        updated_document: dict[str, Any],
        upsert: bool = False,
    ) -> dict[str, Any]:
        result = await self.transient_db.update_one(
            collection,
            filters,
            collection.schema(**updated_document).model_dump(mode="json"),
            upsert,
        )
        await self._process_operation_counter()
        return collection.schema.model_validate(result).model_dump()

    async def delete_one(
        self,
        collection: CollectionDescriptor,
        filters: dict[str, FieldFilter],
    ) -> None:
        await self.transient_db.delete_one(collection, filters)
        await self._process_operation_counter()

    async def flush(self) -> None:
        if self.transient_db:
            data = {}
            for collection_name in await self.transient_db.list_collections():
                data[collection_name] = list(
                    await self.transient_db.find(
                        collection=await self.transient_db.get_collection(collection_name),
                        filters={},
                    )
                )

            await self._save_data(data)
