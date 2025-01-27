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
import json
from pathlib import Path
from typing import Awaitable, Callable, Generic, Optional, Sequence, cast
from typing_extensions import override, Self
import chromadb

from parlant.core.async_utils import ReaderWriterLock
from parlant.core.logging import Logger
from parlant.core.nlp.embedding import Embedder, EmbedderFactory
from parlant.core.persistence.common import Where, ensure_is_total
from parlant.core.persistence.vector_database import (
    BaseDocument,
    DeleteResult,
    InsertResult,
    SimilarDocumentResult,
    UpdateResult,
    VectorCollection,
    VectorDatabase,
    TDocument,
    noop_loader,
)


class ChromaDatabase(VectorDatabase):
    def __init__(
        self,
        logger: Logger,
        dir_path: Path,
        embedder_factory: EmbedderFactory,
    ) -> None:
        self._dir_path = dir_path
        self._logger = logger
        self._embedder_factory = embedder_factory

        self._chroma_client: chromadb.api.ClientAPI
        self._collections: dict[str, ChromaCollection[BaseDocument]] = {}

    async def __aenter__(self) -> Self:
        self._chroma_client = chromadb.PersistentClient(str(self._dir_path))
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[object],
    ) -> None:
        pass

    async def load_documents_to_chroma_collection_with_loader(
        self,
        chroma_collection: chromadb.Collection,
        embedder_type: type[Embedder],
        document_loader: Callable[[BaseDocument], Awaitable[Optional[TDocument]]],
    ) -> chromadb.Collection:
        failed_migrations: list[BaseDocument] = []

        collection_documents = chroma_collection.get()["metadatas"]

        if not collection_documents:
            return chroma_collection

        embedder = self._embedder_factory.create_embedder(embedder_type)

        for doc in collection_documents:
            prospective_doc = cast(BaseDocument, doc)
            try:
                if loaded_doc := await document_loader(prospective_doc):
                    if loaded_doc != prospective_doc:
                        embeddings = list((await embedder.embed([loaded_doc["content"]])).vectors)

                        chroma_collection.update(
                            ids=[prospective_doc["id"]],
                            documents=[loaded_doc["content"]],
                            metadatas=[cast(chromadb.Metadata, loaded_doc)],
                            embeddings=embeddings,
                        )

                else:
                    self._logger.warning(f'Failed to load document "{doc}"')
                    failed_migrations.append(prospective_doc)

            except Exception as e:
                self._logger.error(f"Failed to load document '{doc}' with error: {e}.")
                failed_migrations.append(prospective_doc)

        if failed_migrations:
            failed_migrations_collection = await self.get_or_create_collection(
                "failed_migrations",
                BaseDocument,
                embedder_type,
                noop_loader,
            )

            for failed_doc in failed_migrations:
                failed_migrations_collection.chroma_collection.add(
                    ids=[failed_doc["id"]],
                    documents=[failed_doc["content"]],
                    metadatas=[cast(chromadb.Metadata, failed_doc)],
                    embeddings=[],
                )

        return chroma_collection

    @override
    async def create_collection(
        self,
        name: str,
        schema: type[TDocument],
        embedder_type: type[Embedder],
    ) -> ChromaCollection[TDocument]:
        if name in self._collections:
            raise ValueError(f'Collection "{name}" already exists.')

        self._collections[name] = ChromaCollection(
            self._logger,
            chromadb_collection=self._chroma_client.create_collection(
                name=name,
                embedding_function=None,
            ),
            name=name,
            schema=schema,
            embedder=self._embedder_factory.create_embedder(embedder_type),
        )

        return cast(ChromaCollection[TDocument], self._collections[name])

    @override
    async def get_collection(
        self,
        name: str,
        embedder_type: type[Embedder],
        document_loader: Callable[[BaseDocument], Awaitable[Optional[TDocument]]],
    ) -> ChromaCollection[TDocument]:
        if collection := self._collections.get(name):
            return cast(ChromaCollection[TDocument], collection)
        elif chroma_collection := next(
            (col for col in self._chroma_client.list_collections() if col.name == name), None
        ):
            self._collections[name] = ChromaCollection(
                self._logger,
                chromadb_collection=await self.load_documents_to_chroma_collection_with_loader(
                    chroma_collection, embedder_type=embedder_type, document_loader=document_loader
                ),
                name=name,
                schema=BaseDocument,
                embedder=self._embedder_factory.create_embedder(embedder_type),
            )
            return cast(ChromaCollection[TDocument], self._collections[name])

        raise ValueError(f'ChromaDB collection "{name}" not found.')

    @override
    async def get_or_create_collection(
        self,
        name: str,
        schema: type[TDocument],
        embedder_type: type[Embedder],
        document_loader: Callable[[BaseDocument], Awaitable[Optional[TDocument]]],
    ) -> ChromaCollection[TDocument]:
        if collection := self._collections.get(name):
            return cast(ChromaCollection[TDocument], collection)
        elif chroma_collection := next(
            (col for col in self._chroma_client.list_collections() if col.name == name), None
        ):
            self._collections[name] = ChromaCollection(
                self._logger,
                chromadb_collection=await self.load_documents_to_chroma_collection_with_loader(
                    chroma_collection, embedder_type=embedder_type, document_loader=document_loader
                ),
                name=name,
                schema=BaseDocument,
                embedder=self._embedder_factory.create_embedder(embedder_type),
            )
            return cast(ChromaCollection[TDocument], self._collections[name])

        self._collections[name] = ChromaCollection(
            self._logger,
            chromadb_collection=self._chroma_client.create_collection(
                name=name,
                embedding_function=None,
            ),
            name=name,
            schema=schema,
            embedder=self._embedder_factory.create_embedder(embedder_type),
        )

        return cast(ChromaCollection[TDocument], self._collections[name])

    @override
    async def delete_collection(
        self,
        name: str,
    ) -> None:
        if name not in self._collections:
            raise ValueError(f'Collection "{name}" not found.')
        self._chroma_client.delete_collection(name=name)
        del self._collections[name]


class ChromaCollection(Generic[TDocument], VectorCollection[TDocument]):
    def __init__(
        self,
        logger: Logger,
        chromadb_collection: chromadb.Collection,
        name: str,
        schema: type[TDocument],
        embedder: Embedder,
    ) -> None:
        self._logger = logger
        self._name = name
        self._schema = schema
        self._embedder = embedder

        self._lock = ReaderWriterLock()
        self.chroma_collection = chromadb_collection

    @override
    async def find(
        self,
        filters: Where,
    ) -> Sequence[TDocument]:
        async with self._lock.reader_lock:
            if metadatas := self.chroma_collection.get(where=cast(chromadb.Where, filters) or None)[
                "metadatas"
            ]:
                return [cast(TDocument, m) for m in metadatas]

        return []

    @override
    async def find_one(
        self,
        filters: Where,
    ) -> Optional[TDocument]:
        async with self._lock.reader_lock:
            if metadatas := self.chroma_collection.get(where=cast(chromadb.Where, filters) or None)[
                "metadatas"
            ]:
                return cast(TDocument, {k: v for k, v in metadatas[0].items()})

        return None

    @override
    async def insert_one(
        self,
        document: TDocument,
    ) -> InsertResult:
        ensure_is_total(document, self._schema)

        embeddings = list((await self._embedder.embed([document["content"]])).vectors)

        async with self._lock.writer_lock:
            self.chroma_collection.add(
                ids=[document["id"]],
                documents=[document["content"]],
                metadatas=[cast(chromadb.Metadata, document)],
                embeddings=embeddings,
            )

        return InsertResult(acknowledged=True)

    @override
    async def update_one(
        self,
        filters: Where,
        params: TDocument,
        upsert: bool = False,
    ) -> UpdateResult[TDocument]:
        async with self._lock.writer_lock:
            if docs := self.chroma_collection.get(where=cast(chromadb.Where, filters) or None)[
                "metadatas"
            ]:
                doc = docs[0]

                if "content" in params:
                    embeddings = list((await self._embedder.embed([params["content"]])).vectors)
                    document = params["content"]
                else:
                    embeddings = list((await self._embedder.embed([str(doc["content"])])).vectors)
                    document = str(doc["content"])

                updated_document = {**doc, **params}

                self.chroma_collection.update(
                    ids=[str(doc["id"])],
                    documents=[document],
                    metadatas=[cast(chromadb.Metadata, updated_document)],
                    embeddings=embeddings,  # type: ignore
                )

                return UpdateResult(
                    acknowledged=True,
                    matched_count=1,
                    modified_count=1,
                    updated_document=cast(TDocument, updated_document),
                )

            elif upsert:
                ensure_is_total(params, self._schema)

                embeddings = list((await self._embedder.embed([params["content"]])).vectors)

                self.chroma_collection.add(
                    ids=[params["id"]],
                    documents=[params["content"]],
                    metadatas=[cast(chromadb.Metadata, params)],
                    embeddings=embeddings,
                )

                return UpdateResult(
                    acknowledged=True,
                    matched_count=0,
                    modified_count=0,
                    updated_document=params,
                )

            return UpdateResult(
                acknowledged=True,
                matched_count=0,
                modified_count=0,
                updated_document=None,
            )

    @override
    async def delete_one(
        self,
        filters: Where,
    ) -> DeleteResult[TDocument]:
        async with self._lock.writer_lock:
            if docs := self.chroma_collection.get(where=cast(chromadb.Where, filters) or None)[
                "metadatas"
            ]:
                if len(docs) > 1:
                    raise ValueError(
                        f"ChromaCollection delete_one: detected more than one document with filters '{filters}'. Aborting..."
                    )
                deleted_document = docs[0]

                self.chroma_collection.delete(where=cast(chromadb.Where, filters) or None)

                return DeleteResult(
                    deleted_count=1,
                    acknowledged=True,
                    deleted_document=cast(TDocument, deleted_document),
                )

            return DeleteResult(
                acknowledged=True,
                deleted_count=0,
                deleted_document=None,
            )

    @override
    async def find_similar_documents(
        self,
        filters: Where,
        query: str,
        k: int,
    ) -> Sequence[SimilarDocumentResult[TDocument]]:
        async with self._lock.reader_lock:
            query_embeddings = list((await self._embedder.embed([query])).vectors)

            docs = self.chroma_collection.query(
                where=cast(chromadb.Where, filters) or None,
                query_embeddings=query_embeddings,
                n_results=k,
            )

            if not docs["metadatas"]:
                return []

            self._logger.debug(
                f"Similar documents found\n{json.dumps(docs['metadatas'][0], indent=2)}"
            )

            assert docs["distances"]
            return [
                SimilarDocumentResult(document=cast(TDocument, m), distance=d)
                for m, d in zip(docs["metadatas"][0], docs["distances"][0])
            ]
