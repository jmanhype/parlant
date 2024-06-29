from abc import ABC, abstractmethod
import asyncio
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Generic, Iterable, TypeVar
import aiofiles

T = TypeVar("T")


class DocumentCollection(ABC, Generic[T]):
    @abstractmethod
    async def add_document(self, collection: str, document_id: str, document: T) -> T:
        pass

    @abstractmethod
    async def read_documents(self, collection: str) -> Iterable[T]:
        pass

    @abstractmethod
    async def read_document(self, collection: str, document_id: str) -> T:
        pass

    @abstractmethod
    async def update_document(self, collection: str, document_id: str, updated_document: T) -> T:
        pass

    async def flush(self) -> None:
        pass


class TransientDocumentCollection(DocumentCollection[T]):
    def __init__(self) -> None:
        self._document_store: dict[str, dict[str, T]] = defaultdict(dict)

    async def add_document(self, collection: str, document_id: str, document: T) -> T:
        self._document_store[collection][document_id] = document
        return document

    async def read_documents(self, collection: str) -> Iterable[T]:
        return self._document_store[collection].values()

    async def read_document(self, collection: str, document_id: str) -> T:
        if document := self._document_store[collection].get(document_id):
            return document
        raise KeyError(f'Document "{document_id}" does not exist in collection "{collection}"')

    async def update_document(self, collection: str, document_id: str, updated_document: T) -> T:
        if document_id in self._document_store[collection]:
            self._document_store[collection][document_id] = updated_document
            return updated_document
        else:
            raise KeyError(f'Document "{document_id}" does not exist in collection "{collection}"')


class JSONFileDocumentCollection(DocumentCollection[T], Generic[T]):
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self._lock = asyncio.Lock()
        if not self.file_path.exists():
            self.file_path.write_text(json.dumps({}))

    @property
    def document_type(self) -> Any:
        return self.__orig_class__.__args__[0]  # type: ignore

    class DateTimeEncoder(json.JSONEncoder):
        def default(
            self,
            obj: Any,
        ) -> Any:
            if isinstance(obj, datetime):
                return obj.isoformat()
            return json.JSONEncoder.default(self, obj)

    def json_datetime_decoder(
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
    ) -> Any:
        async with self._lock:
            async with aiofiles.open(self.file_path, "r") as file:
                data = await file.read()
                return json.loads(data, object_hook=self.json_datetime_decoder)

    def _json_dumps(self, data: dict[str, dict[str, T]]) -> str:
        return json.dumps(
            data,
            ensure_ascii=False,
            indent=4,
            cls=self.DateTimeEncoder,
        )

    async def _save_data(
        self,
        data: dict[str, dict[str, T]],
    ) -> None:
        async with self._lock:
            async with aiofiles.open(self.file_path, mode="w") as file:
                json_string = self._json_dumps(data)
                await file.write(json_string)

    def _document_from_dict(
        self,
        data: Any,
    ) -> T:
        return self.document_type(**data)  # type: ignore

    async def add_document(self, collection: str, document_id: str, document: T) -> T:
        data = await self._load_data()
        if collection not in data:
            data[collection] = {}
        data[collection][document_id] = document.__dict__
        await self._save_data(data)
        return document

    async def read_documents(self, collection: str) -> Iterable[T]:
        data = await self._load_data()
        return (self._document_from_dict(doc) for doc in data.get(collection, {}).values())

    async def read_document(self, collection: str, document_id: str) -> T:
        data = await self._load_data()
        document_data = data.get(collection, {}).get(document_id)
        if document_data:
            return self._document_from_dict(document_data)
        raise KeyError(f"Document with id: {document_id} not found in collection '{collection}'.")

    async def update_document(self, collection: str, document_id: str, updated_document: T) -> T:
        data = await self._load_data()
        if collection not in data or document_id not in data[collection]:
            raise KeyError(f'Document "{document_id}" not found in collection "{collection}"')
        data[collection][document_id] = updated_document.__dict__
        await self._save_data(data)
        return updated_document
