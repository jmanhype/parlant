from pytest import fixture, raises
from typing import AsyncIterator

from lagom import Container

from parlant.adapters.db.transient import TransientDocumentDatabase
from parlant.adapters.vector_db.transient import TransientVectorDatabase
from parlant.core.common import Version
from parlant.core.logging import Logger
from parlant.core.nlp.embedding import Embedder, EmbedderFactory
from parlant.core.nlp.service import NLPService
from parlant.core.persistence.common import ObjectId
from parlant.core.persistence.document_database import BaseDocument
from parlant.core.persistence.vector_database import (
    BaseDocument as VectorBaseDocument,
    VectorDatabase,
)
from parlant.core.persistence.converters import (
    DocumentConverterRegistry,
    DocumentConverterService,
    VectorConverterRegistry,
    VectorConverterService,
    conversion,
    vector_conversion,
)


class DummyDocument(BaseDocument):
    name: str
    description: str


class DummyDocumentV2(BaseDocument):
    name: str
    description: str
    new_field: str


class DummyDocumentV3(BaseDocument):
    name: str
    new_field: str


class DummyVectorDocument(VectorBaseDocument):
    name: str
    description: str


class DummyVectorDocumentV2(VectorBaseDocument):
    name: str
    description: str
    new_field: str


class DummyVectorDocumentV3(VectorBaseDocument):
    name: str
    new_field: str


@fixture
async def transient_db() -> TransientDocumentDatabase:
    return TransientDocumentDatabase()


@fixture
async def embedder_type(container: Container) -> type[Embedder]:
    return type(await container[NLPService].get_embedder())


@fixture
async def transient_vector_db(
    container: Container,
    embedder_type: type[Embedder],
) -> AsyncIterator[TransientVectorDatabase]:
    embedder_factory = EmbedderFactory(container)

    async with TransientVectorDatabase(
        container[Logger],
        embedder_factory=embedder_factory,
        embedder_type=embedder_type,
    ) as db:
        yield db


@fixture
def document_converter_registry() -> DocumentConverterRegistry:
    registry = DocumentConverterRegistry()
    registry.converters["dummy_collection"] = [
        convert_dummy_v1_to_v2,
        convert_dummy_v2_to_v3,
    ]
    return registry


@fixture
def document_converter_service(
    container: Container,
    document_converter_registry: DocumentConverterRegistry,
) -> DocumentConverterService:
    logger = container[Logger]
    return DocumentConverterService(logger, document_converter_registry)


@fixture
def vector_converter_registry() -> VectorConverterRegistry:
    registry = VectorConverterRegistry()
    registry.converters["dummy_vector_collection"] = [
        convert_vector_dummy_v1_to_v2,
        convert_vector_dummy_v2_to_v3,
    ]
    return registry


@fixture
def vector_converter_service(
    container: Container,
    vector_converter_registry: VectorConverterRegistry,
) -> VectorConverterService:
    logger = container[Logger]
    return VectorConverterService(logger, vector_converter_registry)


@conversion
async def convert_dummy_v1_to_v2(doc: DummyDocument) -> DummyDocumentV2:
    return DummyDocumentV2(
        id=doc["id"],
        version=Version.String("2"),
        name=doc["name"],
        description=doc["description"],
        new_field="default value",
    )


@conversion
async def convert_dummy_v2_to_v3(doc: DummyDocumentV2) -> DummyDocumentV3:
    return DummyDocumentV3(
        id=doc["id"],
        version=Version.String("2"),
        name=doc["name"],
        new_field=doc["new_field"],
    )


@vector_conversion
async def convert_vector_dummy_v1_to_v2(doc: DummyVectorDocument) -> DummyVectorDocumentV2:
    return DummyVectorDocumentV2(
        id=doc["id"],
        version=Version.String("2"),
        content=doc["content"],
        name=doc["name"],
        description=doc["description"],
        new_field="default vector value",
    )


@vector_conversion
async def convert_vector_dummy_v2_to_v3(doc: DummyVectorDocumentV2) -> DummyVectorDocumentV3:
    return DummyVectorDocumentV3(
        id=doc["id"],
        version=Version.String("2"),
        content=doc["content"],
        name=doc["name"],
        new_field=doc["new_field"],
    )


async def test_that_get_converters_returns_correct_schemas(
    document_converter_registry: DocumentConverterRegistry,
) -> None:
    converters = await document_converter_registry.get_converters("dummy_collection", DummyDocument)

    assert len(converters) == 2

    assert converters[0].input_schema == DummyDocument
    assert converters[0].output_schema == DummyDocumentV2

    assert converters[1].input_schema == DummyDocumentV2
    assert converters[1].output_schema == DummyDocumentV3


async def test_that_document_entities_are_converted_to_final_output_schema(
    document_converter_service: DocumentConverterService,
    transient_db: TransientDocumentDatabase,
) -> None:
    documents = [
        DummyDocument(
            id=ObjectId("1"),
            version=Version.String("1"),
            name="Test Document",
            description="A description",
        )
    ]

    result = await document_converter_service.convert(
        transient_db, "dummy_collection", DummyDocument, documents
    )

    assert result.schema == DummyDocumentV3
    assert len(result.entities) == 1

    final_doc = result.entities[0]
    assert final_doc["id"] == ObjectId("1")
    assert final_doc.get("name") == "Test Document"
    assert final_doc.get("new_field") == "default value"


async def test_that_when_no_document_converters_are_found_entities_and_schema_are_returned_as_input(
    document_converter_service: DocumentConverterService,
    transient_db: TransientDocumentDatabase,
) -> None:
    documents = [
        DummyDocument(
            id=ObjectId("1"),
            version=Version.String("1"),
            name="Test Document",
            description="A description",
        )
    ]

    result = await document_converter_service.convert(
        transient_db, "nonexistent_collection", DummyDocument, documents
    )

    assert result.schema == DummyDocument
    assert result.entities == documents


async def test_that_unsuccessful_entities_are_stored_during_conversion(
    document_converter_service: DocumentConverterService,
    document_converter_registry: DocumentConverterRegistry,
    transient_db: TransientDocumentDatabase,
) -> None:
    documents = [
        DummyDocument(
            id=ObjectId("1"),
            version=Version.String("1"),
            name="Test Document",
            description="A description",
        )
    ]

    @conversion
    async def failing_conversion(doc: DummyDocument) -> DummyDocumentV2:
        raise RuntimeError("Conversion failed")

    document_converter_registry.converters["dummy_collection"] = [failing_conversion]

    result = await document_converter_service.convert(
        transient_db, "dummy_collection", DummyDocument, documents
    )

    assert len(result.entities) == 0

    unsuccessful_collection = await transient_db.get_or_create_collection(
        "unsuccessful_dummy_collection_DummyDocument", DummyDocument
    )
    unsuccessful_entities = await unsuccessful_collection.find({})
    assert len(unsuccessful_entities) == 1
    assert unsuccessful_entities[0]["id"] == ObjectId("1")


async def test_that_get_converters_returns_complete_conversion_chain(
    vector_converter_registry: VectorConverterRegistry,
) -> None:
    converters = await vector_converter_registry.get_converters(
        "dummy_vector_collection", DummyVectorDocument
    )

    assert len(converters) == 2

    assert converters[0].input_schema == DummyVectorDocument
    assert converters[0].output_schema == DummyVectorDocumentV2

    assert converters[1].input_schema == DummyVectorDocumentV2
    assert converters[1].output_schema == DummyVectorDocumentV3


async def test_that_vector_entities_are_converted_to_final_output_schema(
    vector_converter_service: VectorConverterService,
    transient_vector_db: VectorDatabase,
    embedder_type: type[Embedder],
) -> None:
    documents = [
        DummyVectorDocument(
            id=ObjectId("v1"),
            version=Version.String("1"),
            content="A vector content",
            name="Test Vector Document",
            description="A vector description",
        )
    ]

    result = await vector_converter_service.convert(
        transient_vector_db,
        embedder_type,
        "dummy_vector_collection",
        DummyVectorDocument,
        documents,
    )

    assert result.schema == DummyVectorDocumentV3
    assert len(result.entities) == 1

    final_doc = result.entities[0]
    assert final_doc["id"] == ObjectId("v1")
    assert final_doc.get("name") == "Test Vector Document"
    assert final_doc.get("new_field") == "default vector value"


async def test_vector_conversion_path_not_found(
    vector_converter_registry: VectorConverterRegistry,
) -> None:
    with raises(
        ValueError, match="No vector-converters found starting from schema DummyVectorDocumentV3."
    ):
        await vector_converter_registry.get_converters(
            "dummy_vector_collection", DummyVectorDocumentV3
        )


async def test_vector_failed_conversion_is_logged_and_stored(
    vector_converter_service: VectorConverterService,
    vector_converter_registry: VectorConverterRegistry,
    transient_vector_db: VectorDatabase,
    embedder_type: type[Embedder],
) -> None:
    documents = [
        DummyVectorDocument(
            id=ObjectId("v100"),
            version=Version.String("1"),
            content="Failing vector content",
            name="Failing Vector Document",
            description="Will fail",
        )
    ]

    @vector_conversion
    async def failing_conversion(doc: DummyVectorDocument) -> DummyVectorDocumentV2:
        raise RuntimeError("Conversion failed")

    vector_converter_registry.converters["dummy_vector_collection"] = [failing_conversion]

    result = await vector_converter_service.convert(
        transient_vector_db,
        embedder_type,
        "dummy_vector_collection",
        DummyVectorDocument,
        documents,
    )

    assert len(result.entities) == 0

    unsuccessful_collection = await transient_vector_db.get_or_create_collection(
        "unsuccessful_dummy_vector_collection_DummyVectorDocument",
        DummyVectorDocument,
        embedder_type,
    )
    unsuccessful_entities = await unsuccessful_collection.find({})
    assert len(unsuccessful_entities) == 1
    assert unsuccessful_entities[0]["id"] == ObjectId("v100")
