from __future__ import annotations
from abc import ABC, abstractmethod
import asyncio
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Callable, Iterable, Optional, Type, TypedDict
import aiofiles

from emcie.server.core import common


class FieldFilter(TypedDict, total=False):
    equal_to: Any
    not_equal_to: Any
    greater_than: Any
    greater_than_or_equal_to: Any
    less_than: Any
    less_than_or_equal_to: Any
    regex: str


class DocumentDatabase(ABC):

    @abstractmethod
    async def insert_one(
        self,
        collection: str,
        document: dict[str, Any],
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def find(
        self,
        collection: str,
        filters: dict[str, FieldFilter],
    ) -> Iterable[dict[str, Any]]: ...

    @abstractmethod
    async def find_one(
        self,
        collection: str,
        filters: dict[str, FieldFilter],
    ) -> dict[str, Any]:
        """
        Returns the first document that matches the query criteria.
        """

    ...

    @abstractmethod
    async def update_one(
        self,
        collection: str,
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
        collection: str,
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

    async def insert_one(
        self,
        collection: str,
        document: dict[str, Any],
    ) -> dict[str, Any]:
        doc_id = common.generate_id()
        document["id"] = doc_id
        self._collections[collection].append(document)
        return document

    async def find(
        self,
        collection: str,
        filters: dict[str, FieldFilter],
    ) -> Iterable[dict[str, Any]]:
        return filter(lambda d: _matches_filters(filters, d), self._collections[collection])

    async def find_one(
        self,
        collection: str,
        filters: dict[str, FieldFilter],
    ) -> dict[str, Any]:
        matched_documents = list(await self.find(collection, filters))
        if len(matched_documents) >= 1:
            return matched_documents[0]
        raise ValueError("No document found matching the provided filters.")

    async def update_one(
        self,
        collection: str,
        filters: dict[str, FieldFilter],
        updated_document: dict[str, Any],
        upsert: bool = False,
    ) -> dict[str, Any]:
        for i, d in enumerate(self._collections[collection]):
            if _matches_filters(filters, d):
                self._collections[collection][i] = updated_document
                return updated_document
        if upsert:
            document = await self.insert_one(collection, updated_document)
            return document

        raise ValueError("No document found matching the provided filters.")

    async def delete_one(
        self,
        collection: str,
        filters: dict[str, FieldFilter],
    ) -> None:
        for i, d in enumerate(self._collections[collection]):
            if _matches_filters(filters, d):
                del self._collections[collection][i]
                return
        raise ValueError("No document found matching the provided filters.")

    async def list_collections(self) -> Iterable[str]:
        return self._collections.keys()


class JSONFileDocumentDatabase(DocumentDatabase):
    class DateTimeEncoder(json.JSONEncoder):
        def default(
            self,
            obj: Any,
        ) -> Any:
            if isinstance(obj, datetime):
                return obj.isoformat()
            return json.JSONEncoder.default(self, obj)

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self._lock = asyncio.Lock()
        if not self.file_path.exists():
            self.file_path.write_text(json.dumps({}))
        self.transient_db: Optional[TransientDocumentDatabase]

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

    def _json_datetime_decoder(
        self,
        data: Any,
    ) -> Any:
        for key, value in data.items():
            if isinstance(value, str):
                try:
                    data[key] = datetime.fromisoformat(value)
                except ValueError:
                    pass
        return data

    async def _load_data(
        self,
    ) -> dict[str, list[dict[str, Any]]]:
        async with self._lock:
            # Return an empty JSON object if the file is empty
            if self.file_path.stat().st_size == 0:
                return {}

            async with aiofiles.open(self.file_path, "r") as file:
                data = await file.read()
                json_data: dict[str, Any] = json.loads(
                    data, object_hook=self._json_datetime_decoder
                )
                return json_data

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
                    cls=self.DateTimeEncoder,
                )
                await file.write(json_string)

    async def insert_one(
        self,
        collection: str,
        document: dict[str, Any],
    ) -> dict[str, Any]:
        if self.transient_db:
            return await self.transient_db.insert_one(collection, document)
        doc_id = common.generate_id()
        document["id"] = doc_id

        data = await self._load_data()

        if collection in data:
            data[collection].append(document)
        else:
            data[collection] = [document]
        await self._save_data(data)

        return document

    async def find(
        self,
        collection: str,
        filters: dict[str, FieldFilter],
    ) -> Iterable[dict[str, Any]]:
        if self.transient_db:
            return await self.transient_db.find(collection, filters)
        data = await self._load_data()
        return filter(lambda doc: _matches_filters(filters, doc), data.get(collection, []))

    async def find_one(
        self,
        collection: str,
        filters: dict[str, FieldFilter],
    ) -> dict[str, Any]:
        if self.transient_db:
            return await self.transient_db.find_one(collection, filters)
        matched_documents = list(await self.find(collection, filters))
        if len(matched_documents) >= 1:
            return matched_documents[0]
        raise ValueError("No document found matching the provided filters.")

    async def update_one(
        self,
        collection: str,
        filters: dict[str, FieldFilter],
        updated_document: dict[str, Any],
        upsert: bool = False,
    ) -> dict[str, Any]:
        if self.transient_db:
            return await self.transient_db.update_one(collection, filters, updated_document, upsert)
        data = await self._load_data()

        for i, d in enumerate(data.get(collection, [])):
            if _matches_filters(filters, d):
                data[collection][i] = updated_document
                await self._save_data(data)
                return updated_document
        if upsert:
            document = await self.insert_one(collection, updated_document)
            return document
        raise ValueError("No document found matching the provided filters.")

    async def delete_one(
        self,
        collection: str,
        filters: dict[str, FieldFilter],
    ) -> None:
        if self.transient_db:
            return await self.transient_db.delete_one(collection, filters)
        data = await self._load_data()

        for i, d in enumerate(data.get(collection, [])):
            if _matches_filters(filters, d):
                del data[collection][i]
                await self._save_data(data)
                return
        raise ValueError("No document found matching the provided filters.")

    async def flush(self) -> None:
        if self.transient_db:
            data = {}
            for collection_name in await self.transient_db.list_collections():
                data[collection_name] = list(
                    await self.transient_db.find(
                        collection=collection_name,
                        filters={},
                    )
                )

            await self._save_data(data)
