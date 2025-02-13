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

from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import AsyncIterator, Iterator, Optional, TypedDict, cast
import numpy as np
from typing_extensions import Required
from lagom import Container
from pytest import fixture, raises
from chromadb.api.types import IncludeEnum

from parlant.adapters.nlp.openai import OpenAITextEmbedding3Large
from parlant.adapters.vector_db.chroma import ChromaCollection, ChromaDatabase
from parlant.core.agents import AgentStore, AgentId
from parlant.core.common import Version, md5_checksum
from parlant.core.glossary import GlossaryVectorStore
from parlant.core.nlp.embedding import EmbedderFactory, NoOpEmbedder
from parlant.core.logging import Logger
from parlant.core.nlp.service import NLPService
from parlant.core.persistence.common import MigrationError, ObjectId

from parlant.core.persistence.vector_database import BaseDocument
from tests.test_utilities import SyncAwaiter


class _TestDocument(TypedDict, total=False):
    id: Required[ObjectId]
    version: Required[Version.String]
    content: Required[str]
    checksum: Required[str]
    name: str


@dataclass(frozen=True)
class _TestContext:
    home_dir: Path
    container: Container


@fixture
def agent_id(
    container: Container,
    sync_await: SyncAwaiter,
) -> AgentId:
    store = container[AgentStore]
    agent = sync_await(store.create_agent(name="test-agent", max_engine_iterations=2))
    return agent.id


@fixture
def context(container: Container) -> Iterator[_TestContext]:
    with tempfile.TemporaryDirectory() as home_dir:
        home_dir_path = Path(home_dir)
        yield _TestContext(
            container=container,
            home_dir=home_dir_path,
        )


@fixture
def doc_version() -> Version.String:
    return Version.from_string("0.1.0").to_string()


@fixture
async def chroma_database(context: _TestContext) -> AsyncIterator[ChromaDatabase]:
    async with create_database(context) as chroma_database:
        yield chroma_database


def create_database(context: _TestContext) -> ChromaDatabase:
    return ChromaDatabase(
        logger=context.container[Logger],
        dir_path=context.home_dir,
        embedder_factory=EmbedderFactory(context.container),
    )


@fixture
async def chroma_collection(
    chroma_database: ChromaDatabase,
) -> AsyncIterator[ChromaCollection[_TestDocument]]:
    collection = await chroma_database.get_or_create_collection(
        "test_collection",
        _TestDocument,
        embedder_type=OpenAITextEmbedding3Large,
        document_loader=_identity_loader,
    )
    yield collection
    await chroma_database.delete_collection("test_collection")


async def test_that_a_document_can_be_found_based_on_a_metadata_field(
    chroma_collection: ChromaCollection[_TestDocument],
    doc_version: Version.String,
) -> None:
    doc = _TestDocument(
        id=ObjectId("1"),
        version=doc_version,
        content="test content",
        name="test name",
        checksum="test content",
    )

    await chroma_collection.insert_one(doc)

    find_by_id_result = await chroma_collection.find({"id": {"$eq": "1"}})

    assert len(find_by_id_result) == 1

    assert find_by_id_result[0] == doc

    find_one_result = await chroma_collection.find_one({"id": {"$eq": "1"}})

    assert find_one_result == doc

    find_by_name_result = await chroma_collection.find({"name": {"$eq": "test name"}})

    assert len(find_by_name_result) == 1
    assert find_by_name_result[0] == doc

    find_by_not_existing_name_result = await chroma_collection.find(
        {"name": {"$eq": "not existing"}}
    )

    assert len(find_by_not_existing_name_result) == 0


async def test_that_update_one_without_upsert_updates_existing_document(
    chroma_collection: ChromaCollection[_TestDocument],
    doc_version: Version.String,
) -> None:
    document = _TestDocument(
        id=ObjectId("1"),
        version=doc_version,
        content="test content",
        name="test name",
        checksum=md5_checksum("test content"),
    )

    await chroma_collection.insert_one(document)

    updated_document = _TestDocument(
        id=ObjectId("1"),
        version=doc_version,
        content="test content",
        name="new name",
        checksum=md5_checksum("test content"),
    )

    await chroma_collection.update_one(
        {"name": {"$eq": "test name"}},
        updated_document,
        upsert=False,
    )

    result = await chroma_collection.find({"name": {"$eq": "test name"}})
    assert len(result) == 0

    result = await chroma_collection.find({"name": {"$eq": "new name"}})
    assert len(result) == 1
    assert result[0] == updated_document


async def test_that_update_one_without_upsert_and_no_preexisting_document_with_same_id_does_not_insert(
    chroma_collection: ChromaCollection[_TestDocument],
    doc_version: Version.String,
) -> None:
    updated_document = _TestDocument(
        id=ObjectId("1"),
        version=doc_version,
        content="test content",
        name="test name",
        checksum=md5_checksum("test content"),
    )

    result = await chroma_collection.update_one(
        {"name": {"$eq": "new name"}},
        updated_document,
        upsert=False,
    )

    assert result.matched_count == 0
    assert 0 == len(await chroma_collection.find({}))


async def test_that_update_one_with_upsert_and_no_preexisting_document_with_same_id_does_insert_new_document(
    chroma_collection: ChromaCollection[_TestDocument],
    doc_version: Version.String,
) -> None:
    updated_document = _TestDocument(
        id=ObjectId("1"),
        version=doc_version,
        content="test content",
        name="test name",
        checksum=md5_checksum("test content"),
    )

    await chroma_collection.update_one(
        {"name": {"$eq": "test name"}},
        updated_document,
        upsert=True,
    )

    result = await chroma_collection.find({"name": {"$eq": "test name"}})

    assert len(result) == 1
    assert result[0] == updated_document


async def test_delete_one(
    chroma_collection: ChromaCollection[_TestDocument],
    doc_version: Version.String,
) -> None:
    document = _TestDocument(
        id=ObjectId("1"),
        version=doc_version,
        content="test content",
        name="test name",
        checksum=md5_checksum("test content"),
    )

    await chroma_collection.insert_one(document)

    result = await chroma_collection.find({"id": {"$eq": "1"}})
    assert len(result) == 1

    deleted_result = await chroma_collection.delete_one({"id": {"$eq": "1"}})

    assert deleted_result.deleted_count == 1

    if deleted_result.deleted_document:
        assert deleted_result.deleted_document["id"] == ObjectId("1")

    result = await chroma_collection.find({"id": {"$eq": "1"}})
    assert len(result) == 0


async def test_find_similar_documents(
    chroma_collection: ChromaCollection[_TestDocument],
    doc_version: Version.String,
) -> None:
    apple_document = _TestDocument(
        id=ObjectId("1"),
        version=doc_version,
        content="apple",
        name="Apple",
        checksum=md5_checksum("apple"),
    )

    banana_document = _TestDocument(
        id=ObjectId("2"),
        version=doc_version,
        content="banana",
        name="Banana",
        checksum=md5_checksum("banana"),
    )

    cherry_document = _TestDocument(
        id=ObjectId("3"),
        version=doc_version,
        content="cherry",
        name="Cherry",
        checksum=md5_checksum("cherry"),
    )

    await chroma_collection.insert_one(apple_document)
    await chroma_collection.insert_one(banana_document)
    await chroma_collection.insert_one(cherry_document)
    await chroma_collection.insert_one(
        _TestDocument(
            id=ObjectId("4"),
            version=doc_version,
            content="date",
            name="Date",
            checksum=md5_checksum("date"),
        )
    )
    await chroma_collection.insert_one(
        _TestDocument(
            id=ObjectId("5"),
            version=doc_version,
            content="elderberry",
            name="Elderberry",
            checksum=md5_checksum("elderberry"),
        )
    )

    query = "apple banana cherry"
    k = 3

    result = [s.document for s in await chroma_collection.find_similar_documents({}, query, k)]

    assert len(result) == 3
    assert apple_document in result
    assert banana_document in result
    assert cherry_document in result


async def test_loading_collections(
    context: _TestContext,
    doc_version: Version.String,
) -> None:
    async with create_database(context) as first_db:
        created_collection = await first_db.get_or_create_collection(
            "test_collection",
            _TestDocument,
            embedder_type=OpenAITextEmbedding3Large,
            document_loader=_identity_loader,
        )

        document = _TestDocument(
            id=ObjectId("1"),
            version=doc_version,
            content="test content",
            name="test name",
            checksum=md5_checksum("test content"),
        )

        await created_collection.insert_one(document)

    async with create_database(context) as second_db:
        fetched_collection: ChromaCollection[_TestDocument] = await second_db.get_collection(
            "test_collection",
            _TestDocument,
            embedder_type=OpenAITextEmbedding3Large,
            document_loader=_identity_loader,
        )

        result = await fetched_collection.find({"id": {"$eq": "1"}})

        assert len(result) == 1
        assert result[0] == document


async def test_that_glossary_chroma_store_correctly_finds_relevant_terms_from_large_query_input(
    container: Container,
    agent_id: AgentId,
) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        async with ChromaDatabase(
            container[Logger], Path(temp_dir), EmbedderFactory(container)
        ) as chroma_db:
            async with GlossaryVectorStore(
                chroma_db,
                embedder_factory=EmbedderFactory(container),
                embedder_type=type(await container[NLPService].get_embedder()),
            ) as glossary_chroma_store:
                bazoo = await glossary_chroma_store.create_term(
                    term_set=agent_id,
                    name="Bazoo",
                    description="a type of cow",
                )

                shazoo = await glossary_chroma_store.create_term(
                    term_set=agent_id,
                    name="Shazoo",
                    description="a type of zebra",
                )

                kazoo = await glossary_chroma_store.create_term(
                    term_set=agent_id,
                    name="Kazoo",
                    description="a type of horse",
                )

                terms = await glossary_chroma_store.find_relevant_terms(
                    agent_id,
                    ("walla " * 5000)
                    + "Kazoo"
                    + ("balla " * 5000)
                    + "Shazoo"
                    + ("kalla " * 5000)
                    + "Bazoo",
                    max_terms=3,
                )

                assert len(terms) == 3
                assert any(t == kazoo for t in terms)
                assert any(t == shazoo for t in terms)
                assert any(t == bazoo for t in terms)


class _TestDocumentV2(BaseDocument):
    new_name: str


async def _identity_loader(doc: BaseDocument) -> _TestDocument:
    return cast(_TestDocument, doc)


async def test_that_when_persistence_and_store_version_match_allows_store_to_open_when_migrate_is_disabled(
    context: _TestContext,
) -> None:
    async with create_database(context) as chroma_db:
        async with GlossaryVectorStore(
            vector_db=chroma_db,
            embedder_factory=EmbedderFactory(context.container),
            embedder_type=NoOpEmbedder,
            allow_migration=False,
        ):
            metadata = await chroma_db.read_metadata()

            assert metadata
            assert metadata["version"] == GlossaryVectorStore.VERSION.to_string()


async def test_that_document_loader_updates_documents_in_current_chroma_collection(
    context: _TestContext,
) -> None:
    async def _document_loader(doc: BaseDocument) -> _TestDocumentV2:
        if doc["version"] == Version.String("1.0.0"):
            doc_1 = cast(_TestDocument, doc)

            return _TestDocumentV2(
                id=doc_1["id"],
                version=Version.String("2.0.0"),
                content=doc_1["content"],
                checksum=md5_checksum(doc_1["content"] + doc_1["name"]),
                new_name=doc_1["name"],
            )

        if doc["version"] == Version.String("2.0.0"):
            return cast(_TestDocumentV2, doc)

        raise ValueError(f"Version {doc['version']} not supported")

    async with create_database(context) as chroma_database:
        collection = await chroma_database.get_or_create_collection(
            "test_collection",
            _TestDocument,
            embedder_type=OpenAITextEmbedding3Large,
            document_loader=_identity_loader,
        )

        documents = [
            _TestDocument(
                id=ObjectId("1"),
                version=Version.String("1.0.0"),
                content="strawberry",
                name="Document 1",
                checksum=md5_checksum("strawberry"),
            ),
            _TestDocument(
                id=ObjectId("2"),
                version=Version.String("1.0.0"),
                content="apple",
                name="Document 2",
                checksum=md5_checksum("apple"),
            ),
            _TestDocument(
                id=ObjectId("3"),
                version=Version.String("1.0.0"),
                content="cherry",
                name="Document 3",
                checksum=md5_checksum("cherry"),
            ),
        ]

        for doc in documents:
            await collection.insert_one(doc)

    async with create_database(context) as chroma_database:
        new_collection = await chroma_database.get_or_create_collection(
            "test_collection",
            _TestDocumentV2,
            embedder_type=OpenAITextEmbedding3Large,
            document_loader=_document_loader,
        )

        new_documents = await new_collection.find({})
        assert len(new_documents) == 3
        assert new_documents[0]["id"] == ObjectId("1")
        assert new_documents[0]["content"] == "strawberry"
        assert new_documents[0]["new_name"] == "Document 1"
        assert new_documents[0]["version"] == Version.String("2.0.0")
        assert new_documents[0]["checksum"] == md5_checksum("strawberryDocument 1")


async def test_that_failed_migrations_are_stored_in_failed_migrations_collection(
    context: _TestContext,
) -> None:
    async with create_database(context) as chroma_database:
        collection = await chroma_database.get_or_create_collection(
            "test_collection",
            _TestDocument,
            embedder_type=OpenAITextEmbedding3Large,
            document_loader=_identity_loader,
        )

        documents = [
            _TestDocument(
                id=ObjectId("1"),
                version=Version.String("1.0.0"),
                content="valid content",
                name="Valid Document",
                checksum=md5_checksum("valid content"),
            ),
            _TestDocument(
                id=ObjectId("2"),
                version=Version.String("1.0.0"),
                content="invalid",
                name="Invalid Document",
                checksum=md5_checksum("invalid"),
            ),
            _TestDocument(
                id=ObjectId("3"),
                version=Version.String("1.0.0"),
                content="another valid content",
                name="Another Valid Document",
                checksum=md5_checksum("another valid content"),
            ),
        ]

        for doc in documents:
            await collection.insert_one(doc)

    async with create_database(context) as chroma_database:

        async def _document_loader(doc: BaseDocument) -> Optional[_TestDocumentV2]:
            doc_1 = cast(_TestDocument, doc)
            if doc_1["content"] == "invalid":
                return None
            return _TestDocumentV2(
                id=doc_1["id"],
                version=Version.String("2.0.0"),
                content=doc_1["content"],
                new_name=doc_1["name"],
                checksum=md5_checksum(doc_1["content"] + doc_1["name"]),
            )

        collection_with_loader = await chroma_database.get_or_create_collection(
            "test_collection",
            _TestDocumentV2,
            embedder_type=OpenAITextEmbedding3Large,
            document_loader=_document_loader,
        )

        valid_documents = await collection_with_loader.find({})
        assert len(valid_documents) == 2

        valid_contents = {doc["content"] for doc in valid_documents}

        assert "valid content" in valid_contents
        assert "another valid content" in valid_contents
        assert "invalid" not in valid_contents

        valid_names = {doc["new_name"] for doc in valid_documents}
        assert "Valid Document" in valid_names
        assert "Another Valid Document" in valid_names

        failed_migrations_collection = await chroma_database.get_or_create_collection(
            "failed_migrations",
            BaseDocument,
            embedder_type=OpenAITextEmbedding3Large,
            document_loader=_identity_loader,
        )

        failed_migrations = await failed_migrations_collection.find({})
        assert len(failed_migrations) == 1

        failed_doc = cast(_TestDocument, failed_migrations[0])
        assert failed_doc["id"] == ObjectId("2")
        assert failed_doc["content"] == "invalid"
        assert failed_doc["name"] == "Invalid Document"


async def test_that_migration_error_raised_when_version_mismatch_and_migration_disabled(
    context: _TestContext,
) -> None:
    async with create_database(context) as chroma_db:
        await chroma_db.upsert_metadata("version", "NotRealVersion")

    async with create_database(context) as chroma_db:
        with raises(MigrationError) as exc_info:
            async with GlossaryVectorStore(
                vector_db=chroma_db,
                embedder_factory=EmbedderFactory(context.container),
                embedder_type=NoOpEmbedder,
                allow_migration=False,
            ):
                pass

        assert "Migration required for GlossaryVectorStore." in str(exc_info.value)


async def test_that_new_store_creates_metadata_with_correct_version(
    context: _TestContext,
) -> None:
    async with create_database(context) as chroma_db:
        async with GlossaryVectorStore(
            vector_db=chroma_db,
            embedder_factory=EmbedderFactory(context.container),
            embedder_type=OpenAITextEmbedding3Large,
            allow_migration=False,
        ):
            metadata = await chroma_db.read_metadata()

            assert metadata
            assert metadata["version"] == GlossaryVectorStore.VERSION.to_string()


async def test_that_documents_are_indexed_when_changing_embedder_type(
    context: _TestContext,
    agent_id: AgentId,
) -> None:
    async with create_database(context) as chroma_db:
        async with GlossaryVectorStore(
            vector_db=chroma_db,
            embedder_factory=EmbedderFactory(context.container),
            embedder_type=OpenAITextEmbedding3Large,
            allow_migration=True,
        ) as store:
            term = await store.create_term(
                term_set=agent_id,
                name="Bazoo",
                description="a type of cow",
            )

    async with create_database(context) as chroma_db:
        async with GlossaryVectorStore(
            vector_db=chroma_db,
            embedder_factory=EmbedderFactory(context.container),
            embedder_type=NoOpEmbedder,
            allow_migration=True,
        ) as store:
            docs = chroma_db.chroma_client.get_collection(name="glossary_NoOpEmbedder").get(
                include=[IncludeEnum.embeddings, IncludeEnum.metadatas]
            )

            assert docs["metadatas"]
            assert len(docs["metadatas"]) == 1

            assert docs["embeddings"] is not None
            embeddings = np.array(docs["embeddings"])
            assert np.all(embeddings == 0)

            assert any(d["id"] == term.id for d in docs["metadatas"])


async def test_that_documents_are_migrated_and_reindexed_for_new_embedder_type(
    context: _TestContext,
) -> None:
    async def _document_loader(doc: BaseDocument) -> _TestDocumentV2:
        doc_1 = cast(_TestDocument, doc)

        return _TestDocumentV2(
            id=doc_1["id"],
            version=Version.String("2.0.0"),
            content=doc_1["content"],
            new_name=doc_1["name"],
            checksum=md5_checksum(doc_1["content"] + doc_1["name"]),
        )

    async with create_database(context) as chroma_database:
        collection = await chroma_database.get_or_create_collection(
            "test_collection",
            _TestDocument,
            embedder_type=OpenAITextEmbedding3Large,
            document_loader=_identity_loader,
        )

        documents = [
            _TestDocument(
                id=ObjectId("1"),
                version=Version.String("1.0.0"),
                content="test content 1",
                name="Document 1",
                checksum=md5_checksum("test content 1"),
            ),
            _TestDocument(
                id=ObjectId("2"),
                version=Version.String("1.0.0"),
                content="test content 2",
                name="Document 2",
                checksum=md5_checksum("test content 2"),
            ),
        ]
        for doc in documents:
            await collection.insert_one(doc)

    async with create_database(context) as chroma_database:
        new_collection = await chroma_database.get_or_create_collection(
            "test_collection",
            _TestDocumentV2,
            embedder_type=NoOpEmbedder,
            document_loader=_document_loader,
        )

        migrated_docs = await new_collection.find({})
        assert len(migrated_docs) == 2
        assert any(
            d["id"] == ObjectId("1") and d["new_name"] == "Document 1" for d in migrated_docs
        )
        assert any(
            d["id"] == ObjectId("2") and d["new_name"] == "Document 2" for d in migrated_docs
        )
        assert all(d["version"] == Version.String("2.0.0") for d in migrated_docs)
