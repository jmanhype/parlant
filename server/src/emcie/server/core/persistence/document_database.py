from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import (
    Any,
    Generic,
    Mapping,
    Optional,
    Sequence,
    Type,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from emcie.server.core.persistence.common import Where


TDocument = TypeVar("TDocument", bound=Mapping[str, Any])


def is_total(document: TDocument, schema: type[TDocument]) -> bool:
    annotations = get_type_hints(schema)
    for key, expected_type in annotations.items():
        if key not in document:
            raise TypeError(f"key '{key}' did not provided.")
        if key in document and not _is_instance_of_type(document[key], expected_type):
            raise TypeError(f"value '{document[key]}' expected to be '{expected_type}'.")
    return True


def _is_instance_of_type(value: Any, expected_type: type) -> bool:
    origin = get_origin(expected_type)
    args = get_args(expected_type)

    if origin is Union:
        return any(_is_instance_of_type(value, arg) for arg in args)

    if origin and issubclass(origin, Sequence):
        if not issubclass(type(value), Sequence):
            return False
        if not args:
            return True
        return all(_is_instance_of_type(item, args[0]) for item in value)

    elif origin and issubclass(origin, Mapping):
        if not issubclass(type(value), Mapping):
            return False
        if not args:
            return True
        key_type, val_type = args
        return all(
            _is_instance_of_type(k, key_type) and _is_instance_of_type(v, val_type)
            for k, v in value.items()
        )
    return isinstance(value, expected_type)


class DocumentDatabase(ABC):
    @abstractmethod
    def create_collection(
        self,
        name: str,
        schema: Type[TDocument],
    ) -> DocumentCollection[TDocument]:
        """
        Creates a new collection with the given name and returns the collection.
        """
        ...

    @abstractmethod
    def get_collection(
        self,
        name: str,
    ) -> DocumentCollection[TDocument]:
        """
        Retrieves an existing collection by its name.
        """
        ...

    @abstractmethod
    def get_or_create_collection(
        self,
        name: str,
        schema: Type[TDocument],
    ) -> DocumentCollection[TDocument]:
        """
        Retrieves an existing collection by its name or creates a new one if it does not exist.
        """
        ...

    @abstractmethod
    def delete_collection(
        self,
        name: str,
    ) -> None:
        """
        Deletes a collection by its name.
        """
        ...


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
