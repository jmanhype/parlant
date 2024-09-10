from __future__ import annotations
from typing import Optional, Sequence, Type, cast
from emcie.server.core.persistence.common import (
    BaseDocument,
    NoMatchingDocumentsError,
    ObjectId,
    Where,
    matches_filters,
)
from emcie.server.core.persistence.document_database import (
    DocumentCollection,
    DocumentDatabase,
    TDocument,
)


class TransientDocumentDatabase(DocumentDatabase):
    def __init__(self) -> None:
        self._collections: dict[str, _TransientDocumentCollection[BaseDocument]] = {}

    def create_collection(
        self,
        name: str,
        schema: Type[TDocument],
    ) -> _TransientDocumentCollection[TDocument]:
        self._collections[name] = _TransientDocumentCollection(
            name=name,
            schema=schema,
        )

        return cast(_TransientDocumentCollection[TDocument], self._collections[name])

    def get_collection(
        self,
        name: str,
    ) -> _TransientDocumentCollection[TDocument]:
        if name in self._collections:
            return cast(_TransientDocumentCollection[TDocument], self._collections[name])
        raise ValueError(f'Collection "{name}" does not exist')

    def get_or_create_collection(
        self,
        name: str,
        schema: Type[TDocument],
    ) -> _TransientDocumentCollection[TDocument]:
        if collection := self._collections.get(name):
            return cast(_TransientDocumentCollection[TDocument], collection)

        return self.create_collection(
            name=name,
            schema=schema,
        )

    def delete_collection(
        self,
        name: str,
    ) -> None:
        if name in self._collections:
            del self._collections[name]
        else:
            raise ValueError(f'Collection "{name}" does not exist')


class _TransientDocumentCollection(DocumentCollection[TDocument]):
    def __init__(
        self,
        name: str,
        schema: Type[TDocument],
        data: Optional[Sequence[TDocument]] = None,
    ) -> None:
        self._name = name
        self._schema = schema
        self._documents = list(data) if data else []

    async def find(
        self,
        filters: Where,
    ) -> Sequence[TDocument]:
        return list(
            filter(
                lambda d: matches_filters(filters, d),
                self._documents,
            )
        )

    async def find_one(
        self,
        filters: Where,
    ) -> TDocument:
        matched_documents = await self.find(filters)
        if len(matched_documents) >= 1:
            return matched_documents[0]
        raise NoMatchingDocumentsError(self._name, filters)

    async def insert_one(
        self,
        document: TDocument,
    ) -> ObjectId:
        self._documents.append(document)

        return document.id

    async def update_one(
        self,
        filters: Where,
        updated_document: TDocument,
        upsert: bool = False,
    ) -> ObjectId:
        for i, d in enumerate(self._documents):
            if matches_filters(filters, d):
                self._documents[i] = updated_document

                return updated_document.id

        if upsert:
            document_id = await self.insert_one(updated_document)
            return document_id

        raise NoMatchingDocumentsError(self._name, filters)

    async def delete_one(
        self,
        filters: Where,
    ) -> TDocument:
        for i, d in enumerate(self._documents):
            if matches_filters(filters, d):
                document = self._documents[i]
                del self._documents[i]

                return document

        raise NoMatchingDocumentsError(self._name, filters)
