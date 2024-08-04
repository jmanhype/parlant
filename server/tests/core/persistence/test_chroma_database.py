from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import AsyncIterator, Iterator
from lagom import Container
from pytest import fixture, mark, raises

from emcie.server.base_models import DefaultBaseModel
from emcie.server.core.persistence.chroma_database import ChromaCollection, ChromaDatabase
from emcie.server.logger import Logger


class _TestModel(DefaultBaseModel):
    id: str
    content: str
    name: str


@dataclass(frozen=True)
class _TestContext:
    home_dir: Path
    logger: Logger


@fixture
def context(container: Container) -> Iterator[_TestContext]:
    with tempfile.TemporaryDirectory() as home_dir:
        home_dir_path = Path(home_dir)
        yield _TestContext(
            logger=container[Logger],
            home_dir=home_dir_path,
        )


@fixture
def chroma_database(context: _TestContext) -> ChromaDatabase:
    return ChromaDatabase(
        logger=context.logger,
        dir_path=context.home_dir,
    )


@fixture
async def chroma_collection(chroma_database: ChromaDatabase) -> AsyncIterator[ChromaCollection]:
    collection = chroma_database.get_or_create_collection("test_collection", _TestModel)
    yield collection
    chroma_database.delete_collection("test_collection")


@mark.asyncio
async def test_that_create_document_and_find_with_metadata_field(
    chroma_collection: ChromaCollection,
) -> None:
    await chroma_collection.insert_one(
        {
            "id": "1",
            "content": "test content",
            "name": "test name",
        },
    )

    find_by_id_result = await chroma_collection.find({"id": {"$eq": "1"}})

    assert len(find_by_id_result) == 1
    assert find_by_id_result == [
        {
            "id": "1",
            "content": "test content",
            "name": "test name",
        }
    ]

    find_one_result = await chroma_collection.find_one({"id": {"$eq": "1"}})

    assert find_one_result == {
        "id": "1",
        "content": "test content",
        "name": "test name",
    }

    find_by_name_result = await chroma_collection.find({"name": {"$eq": "test name"}})

    assert len(find_by_name_result) == 1
    assert find_by_name_result == [
        {
            "id": "1",
            "content": "test content",
            "name": "test name",
        }
    ]

    find_by_not_existing_name_result = await chroma_collection.find(
        {"name": {"$eq": "not existing"}}
    )

    assert len(find_by_not_existing_name_result) == 0


@mark.asyncio
async def test_that_update_one_without_upsert_is_updating_existing_document(
    chroma_collection: ChromaCollection,
) -> None:
    await chroma_collection.insert_one(
        {
            "id": "1",
            "content": "test content",
            "name": "test name",
        },
    )

    updated_document = {
        "id": "1",
        "content": "test content",
        "name": "new name",
    }

    await chroma_collection.update_one(
        {"name": {"$eq": "test name"}},
        updated_document,
        upsert=False,
    )

    result = await chroma_collection.find({"name": {"$eq": "test name"}})

    assert len(result) == 0  # didn't find since it got updated

    result = await chroma_collection.find({"name": {"$eq": "new name"}})

    assert len(result) == 1
    assert result == [
        {
            "id": "1",
            "content": "test content",
            "name": "new name",
        }
    ]


@mark.asyncio
async def test_that_update_one_without_upsert_and_no_existing_content_does_not_insert(
    chroma_collection: ChromaCollection,
) -> None:
    updated_document = {
        "id": "1",
        "content": "test content",
        "name": "new name",
    }

    with raises(ValueError):
        await chroma_collection.update_one(
            {"name": {"$eq": "new name"}},
            updated_document,
            upsert=False,
        )


@mark.asyncio
async def test_that_update_one_with_upsert_and_no_existing_content_inserts_new_document(
    chroma_collection: ChromaCollection,
) -> None:
    updated_document = {
        "id": "1",
        "content": "test content",
        "name": "new name",
    }

    await chroma_collection.update_one(
        {"name": {"$eq": "new name"}},
        updated_document,
        upsert=True,
    )

    result = await chroma_collection.find({"name": {"$eq": "new name"}})

    assert len(result) == 1
    assert result == [
        {
            "id": "1",
            "content": "test content",
            "name": "new name",
        }
    ]


@mark.asyncio
async def test_delete_one(chroma_collection: ChromaCollection) -> None:
    await chroma_collection.insert_one(
        {
            "id": "1",
            "content": "test content",
            "name": "test name",
        },
    )

    result = await chroma_collection.find({"id": {"$eq": "1"}})
    assert len(result) == 1

    await chroma_collection.delete_one({"id": {"$eq": "1"}})

    result = await chroma_collection.find({"id": {"$eq": "1"}})
    assert len(result) == 0


@mark.asyncio
async def test_find_similar_documents(chroma_collection: ChromaCollection) -> None:
    documents = [
        {"id": "1", "content": "apple", "name": "Apple"},
        {"id": "2", "content": "banana", "name": "Banana"},
        {"id": "3", "content": "cherry", "name": "Cherry"},
        {"id": "4", "content": "date", "name": "Date"},
        {"id": "5", "content": "elderberry", "name": "Elderberry"},
    ]

    for doc in documents:
        await chroma_collection.insert_one(doc)

    query = "apple banana cherry"
    k = 3

    result = await chroma_collection.find_similar_documents({}, query, k)

    assert len(result) == 3
    assert {"id": "1", "content": "apple", "name": "Apple"} in result
    assert {"id": "2", "content": "banana", "name": "Banana"} in result
    assert {"id": "3", "content": "cherry", "name": "Cherry"} in result


@mark.asyncio
async def test_loading_collections_succeed(context: _TestContext) -> None:
    # Step 1: Create initial database and collection, then insert a document
    chroma_database_1 = ChromaDatabase(logger=context.logger, dir_path=context.home_dir)
    chroma_collection_1 = chroma_database_1.get_or_create_collection("test_collection", _TestModel)
    await chroma_collection_1.insert_one(
        {
            "id": "1",
            "content": "test content",
            "name": "test name",
        },
    )

    chroma_database_2 = ChromaDatabase(logger=context.logger, dir_path=context.home_dir)
    chroma_collection_2 = chroma_database_2.get_collection("test_collection")

    result = await chroma_collection_2.find({"id": {"$eq": "1"}})

    assert len(result) == 1
    assert result == [
        {
            "id": "1",
            "content": "test content",
            "name": "test name",
        }
    ]
