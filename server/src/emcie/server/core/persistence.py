from abc import ABC, abstractmethod
import asyncio
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Callable, Iterable, TypedDict
import aiofiles

from emcie.server.core import common


class FieldFilter(TypedDict, total=False):
    equal_to: Any
    not_equal_to: Any
    greater_than: Any
    less_than: Any
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
    conditions: dict[str, FieldFilter],
    candidate: dict[str, Any],
) -> bool:
    tests: dict[str, Callable[[Any, Any], bool]] = {
        "equal_to": lambda a, b: a == b,
        "not_equal_to": lambda a, b: a != b,
        "greater_than": lambda a, b: a > b,
        "less_than": lambda a, b: a < b,
        "regex": lambda a, b: bool(re.match(str(a), str(b))),
    }
    for field, field_filter in conditions.items():
        for test_name, test_value in field_filter.items():
            if not tests[test_name](test_value, candidate.get(field)):
                return False
    return True


class TransientDocumentDatabase(DocumentDatabase):
    def __init__(self) -> None:
        self._collections: dict[str, list[dict[str, Any]]] = defaultdict(list)

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


class JSONFileDocumentDatabase(DocumentDatabase):
    class DateTimeEncoder(json.JSONEncoder):
        def default(
            self,
            obj: Any,
        ) -> Any:
            if isinstance(obj, datetime):
                return obj.isoformat()
            return json.JSONEncoder.default(self, obj)

    def __init__(self, file_path: str) -> None:
        self.file_path = Path(file_path)
        self._lock = asyncio.Lock()
        if not self.file_path.exists():
            self.file_path.write_text(json.dumps({}))

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
        data = await self._load_data()
        return filter(lambda doc: _matches_filters(filters, doc), data.get(collection, []))

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
        data = await self._load_data()

        for i, d in enumerate(data.get(collection, [])):
            if _matches_filters(filters, d):
                del data[collection][i]
                await self._save_data(data)
                return
        raise ValueError("No document found matching the provided filters.")

    async def flush(self) -> None:
        raise NotImplementedError
