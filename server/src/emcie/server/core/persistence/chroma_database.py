from __future__ import annotations
import asyncio
import importlib
import json
import operator
import os
from pathlib import Path
from typing import Generic, Sequence, Type, TypeVar, cast
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction  # type: ignore

from emcie.server.core.persistence.common import (
    BaseDocument,
    NoMatchingDocumentsError,
    ObjectId,
    Where,
)
from emcie.server.core.persistence.document_database import DeleteResult, InsertResult, UpdateResult
from emcie.server.logger import Logger


class ChromaDocument(BaseDocument):
    content: str


TChromaDocument = TypeVar("TChromaDocument", bound=ChromaDocument)


class ChromaDatabase:
    def __init__(self, logger: Logger, dir_path: Path) -> None:
        self.logger = logger

        self._chroma_client = chromadb.PersistentClient(str(dir_path))
        self._embedding_function = OpenAIEmbeddingFunction(
            api_key=os.environ.get("OPENAI_API_KEY"),
            model_name="text-embedding-3-large",
        )
        self._collections: dict[str, ChromaCollection[ChromaDocument]] = (
            self._load_chromadb_collections()
        )

    def _load_chromadb_collections(self) -> dict[str, ChromaCollection[ChromaDocument]]:
        collections: dict[str, ChromaCollection[ChromaDocument]] = {}
        for chromadb_collection in self._chroma_client.list_collections():
            collections[chromadb_collection.name] = ChromaCollection(
                logger=self.logger,
                chromadb_collection=chromadb_collection,
                name=chromadb_collection.name,
                schema=operator.attrgetter(chromadb_collection.metadata["model_path"])(
                    importlib.import_module(chromadb_collection.metadata["module_path"])
                ),
            )
        return collections

    def create_collection(
        self,
        name: str,
        schema: Type[TChromaDocument],
    ) -> ChromaCollection[TChromaDocument]:
        if name in self._collections:
            raise ValueError(f'Collection "{name}" already exists.')

        assert issubclass(schema, ChromaDocument)

        self._collections[name] = ChromaCollection(
            self.logger,
            chromadb_collection=self._chroma_client.create_collection(
                name=name,
                embedding_function=self._embedding_function,
                metadata={
                    "module_path": schema.__module__,
                    "model_path": schema.__qualname__,
                },
            ),
            name=name,
            schema=schema,
        )

        return cast(ChromaCollection[TChromaDocument], self._collections[name])

    def get_collection(
        self,
        name: str,
    ) -> ChromaCollection[TChromaDocument]:
        if collection := self._collections.get(name):
            return cast(ChromaCollection[TChromaDocument], collection)

        raise ValueError(f'ChromaDB collection "{name}" not found.')

    def get_or_create_collection(
        self,
        name: str,
        schema: Type[TChromaDocument],
    ) -> ChromaCollection[TChromaDocument]:
        if collection := self._collections.get(name):
            assert schema == collection._schema
            return cast(ChromaCollection[TChromaDocument], collection)

        assert issubclass(schema, ChromaDocument)

        self._collections[name] = ChromaCollection(
            self.logger,
            chromadb_collection=self._chroma_client.create_collection(
                name=name,
                embedding_function=self._embedding_function,
                metadata={
                    "module_path": schema.__module__,
                    "model_path": schema.__qualname__,
                },
            ),
            name=name,
            schema=schema,
        )

        return cast(ChromaCollection[TChromaDocument], self._collections[name])

    def delete_collection(
        self,
        name: str,
    ) -> None:
        if name not in self._collections:
            raise ValueError(f'Collection "{name}" not found.')
        self._chroma_client.delete_collection(name=name)
        del self._collections[name]


class ChromaCollection(Generic[TChromaDocument]):
    def __init__(
        self,
        logger: Logger,
        chromadb_collection: chromadb.Collection,
        name: str,
        schema: Type[TChromaDocument],
    ) -> None:
        self.logger = logger
        self._name = name
        self._schema = schema
        self._lock = asyncio.Lock()
        self._chroma_collection = chromadb_collection

    async def find(
        self,
        filters: Where,
    ) -> Sequence[TChromaDocument]:
        if metadatas := self._chroma_collection.get(where=cast(chromadb.Where, filters))[
            "metadatas"
        ]:
            return [self._schema.model_validate(m) for m in metadatas]

        return []

    async def find_one(
        self,
        filters: Where,
    ) -> TChromaDocument:
        if metadatas := self._chroma_collection.get(where=cast(chromadb.Where, filters))[
            "metadatas"
        ]:
            return self._schema.model_validate({k: v for k, v in metadatas[0].items()})

        raise NoMatchingDocumentsError(self._name, filters)

    async def insert_one(
        self,
        document: TChromaDocument,
    ) -> InsertResult:
        async with self._lock:
            self._chroma_collection.add(
                ids=[document.id],
                documents=[document.content],
                metadatas=[document.model_dump(mode="json")],
            )

        return InsertResult(document.id, acknowledged=True)

    async def update_one(
        self,
        filters: Where,
        updated_document: TChromaDocument,
        upsert: bool = False,
    ) -> UpdateResult:
        async with self._lock:
            if docs := self._chroma_collection.get(where=cast(chromadb.Where, filters))[
                "metadatas"
            ]:
                document_id = ObjectId(str(docs[0]["id"]))

                self._chroma_collection.update(
                    ids=[document_id],
                    documents=[updated_document.content],
                    metadatas=[
                        self._schema(
                            **{**docs[0], **updated_document.model_dump(mode="json")}
                        ).model_dump(mode="json")
                    ],
                )

                return UpdateResult(
                    matched_count=1,
                    modified_count=1,
                    upserted_id=None,
                )

            elif upsert:
                self._chroma_collection.add(
                    ids=[updated_document.id],
                    documents=[updated_document.content],
                    metadatas=[updated_document.model_dump(mode="json")],
                )

                return UpdateResult(
                    matched_count=0,
                    modified_count=0,
                    upserted_id=updated_document.id,
                )

            raise NoMatchingDocumentsError(self._name, filters)

    async def delete_one(
        self,
        filters: Where,
    ) -> DeleteResult:
        async with self._lock:
            docs = self._chroma_collection.get(where=cast(chromadb.Where, filters))["metadatas"]
            if docs:
                if len(docs) > 1:
                    raise ValueError(
                        f"ChromaCollection delete_one: detected more than one document with filters '{filters}'. Aborting..."
                    )

                self._chroma_collection.delete(where=cast(chromadb.Where, filters))

                return DeleteResult(deleted_count=1, acknowledged=True)

            else:
                raise NoMatchingDocumentsError(self._name, filters)

    async def find_similar_documents(
        self,
        filters: Where,
        query: str,
        k: int,
    ) -> Sequence[TChromaDocument]:
        docs = self._chroma_collection.query(
            where=cast(chromadb.Where, filters),
            query_texts=[query],
            n_results=k,
        )

        if metadatas := docs["metadatas"]:
            self.logger.debug(f"Similar documents found: {json.dumps(metadatas[0], indent=2)}")

            return [self._schema.model_validate(m) for m in metadatas[0]]

        return []
