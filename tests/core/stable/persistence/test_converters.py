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

from typing import cast
from lagom import Container
from pytest import fixture, raises
from parlant.adapters.db.transient import TransientDocumentDatabase
from parlant.core.common import Version
from parlant.core.logging import Logger
from parlant.core.persistence.converters import (
    Converter,
    DocumentConverterRegistry,
    DocumentConverterService,
)
from parlant.core.persistence.common import ObjectId
from parlant.core.persistence.document_database import (
    BaseDocument,
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


class ConverterV1ToV2(Converter):
    @property
    def from_version(self) -> Version.String:
        return Version.String("1.0.0")

    @property
    def to_version(self) -> Version.String:
        return Version.String("2.0.0")

    async def convert(self, entity: BaseDocument) -> DummyDocumentV2:
        dummy_doc = cast(DummyDocument, entity)
        return DummyDocumentV2(
            id=dummy_doc["id"],
            version=self.to_version,
            name=dummy_doc["name"],
            description=dummy_doc["description"],
            new_field="default value",
        )


class ConverterV2ToV3(Converter):
    @property
    def from_version(self) -> Version.String:
        return Version.String("2.0.0")

    @property
    def to_version(self) -> Version.String:
        return Version.String("3.0.0")

    async def convert(self, entity: BaseDocument) -> DummyDocumentV3:
        dummy_doc = cast(DummyDocumentV2, entity)
        return DummyDocumentV3(
            id=dummy_doc["id"],
            version=self.to_version,
            name=dummy_doc["name"],
            new_field=dummy_doc["new_field"],
        )


@fixture
def document_converter_registry() -> DocumentConverterRegistry:
    database = TransientDocumentDatabase()
    registry = DocumentConverterRegistry(database)

    # Register converters
    registry.converters["dummy_collection"] = [
        ConverterV1ToV2(),
        ConverterV2ToV3(),
    ]
    return registry


@fixture
def document_converter_service(
    container: Container,
    document_converter_registry: DocumentConverterRegistry,
) -> DocumentConverterService:
    logger = container[Logger]
    database = document_converter_registry._database
    return DocumentConverterService(logger, database, document_converter_registry)


async def test_get_converters_returns_correct_path(
    document_converter_registry: DocumentConverterRegistry,
) -> None:
    converters = await document_converter_registry.get_converters(
        "dummy_collection", Version.String("1.0.0")
    )
    assert len(converters) == 2
    assert converters[0].from_version == Version.String("1.0.0")
    assert converters[1].from_version == Version.String("2.0.0")


async def test_successful_conversion(document_converter_service: DocumentConverterService) -> None:
    documents = [
        DummyDocument(
            id=ObjectId("1"),
            version=Version.from_string("1.0.0").to_string(),
            name="Test Document",
            description="This is a test document.",
        )
    ]

    converted_documents = await document_converter_service.convert(
        "dummy_collection", documents, DummyDocumentV3
    )

    assert len(converted_documents) == 1
    assert converted_documents[0].get("id") == ObjectId("1")
    assert converted_documents[0].get("version") == "3.0.0"
    assert converted_documents[0].get("name") == "Test Document"


async def test_conversion_path_not_found(
    document_converter_registry: DocumentConverterRegistry,
) -> None:
    with raises(ValueError, match="No converters found starting from version 4.0.0."):
        await document_converter_registry.get_converters(
            "dummy_collection", Version.String("4.0.0")
        )


async def test_failed_conversion_is_logged_and_stored(
    document_converter_service: DocumentConverterService,
    document_converter_registry: DocumentConverterRegistry,
) -> None:
    documents = [
        DummyDocument(
            id=ObjectId("1"),
            version=Version.from_string("2.0.0").to_string(),
            name="Test Document",
            description="This is a test document.",
        )
    ]

    class FailingConverter(Converter):
        @property
        def from_version(self) -> Version.String:
            return Version.String("2.0.0")

        @property
        def to_version(self) -> Version.String:
            return Version.String("3.0.0")

        async def convert(self, entity: BaseDocument) -> DummyDocumentV3:
            raise RuntimeError("Conversion failed.")

    document_converter_registry.converters["dummy_collection"] = [FailingConverter()]

    converted_documents = await document_converter_service.convert(
        "dummy_collection", documents, DummyDocumentV3
    )

    assert len(converted_documents) == 0

    unsuccessful_collection = await document_converter_service._database.get_or_create_collection(
        "unsuccessful_dummy_collection", DummyDocument
    )
    unsuccessful_entities = await unsuccessful_collection.find({})
    assert len(unsuccessful_entities) == 1
    assert unsuccessful_entities[0].get("id") == "1"
