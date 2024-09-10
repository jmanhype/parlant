from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Generic, Sequence, Type, TypeVar

from emcie.server.core.persistence.common import BaseDocument, ObjectId, Where


TDocument = TypeVar("TDocument", bound=BaseDocument)


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
    ) -> TDocument:
        """Returns the first document that matches the query criteria."""
        ...

    @abstractmethod
    async def insert_one(
        self,
        document: TDocument,
    ) -> ObjectId:
        """Inserts a single document into the collection."""
        ...

    @abstractmethod
    async def update_one(
        self,
        filters: Where,
        updated_document: TDocument,
        upsert: bool = False,
    ) -> ObjectId:
        """Updates the first document that matches the query criteria. If upsert is True,
        inserts the document if it does not exist."""
        ...

    @abstractmethod
    async def delete_one(
        self,
        filters: Where,
    ) -> TDocument:
        """Deletes the first document that matches the query criteria."""
        ...
