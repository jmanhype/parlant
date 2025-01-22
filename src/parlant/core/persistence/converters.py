from abc import ABC, abstractmethod
from typing import Sequence, TypeVar
from typing_extensions import override

from parlant.core.common import Version
from parlant.core.logging import Logger
from parlant.core.persistence.document_database import (
    BaseDocument,
    DocumentCollection,
    DocumentDatabase,
)
from parlant.core.persistence.vector_database import BaseDocument as VectorBaseDocument


TInput = TypeVar("TInput", BaseDocument, VectorBaseDocument)
TOutput = TypeVar("TOutput", BaseDocument, VectorBaseDocument)


class Converter(ABC):
    @property
    @abstractmethod
    def from_version(self) -> Version.String: ...

    @property
    @abstractmethod
    def to_version(self) -> Version.String: ...

    @abstractmethod
    async def convert(self, entity: BaseDocument) -> BaseDocument:
        """
        Converts a entity from one version to the next.
        """
        ...


class ConverterRegistry(ABC):
    """Abstract base class for managing converters."""

    @abstractmethod
    async def get_converters(
        self,
        collection_name: str,
        from_version: Version.String,
    ) -> Sequence[Converter]: ...


class DocumentConverterRegistry(ConverterRegistry):
    def __init__(self, database: DocumentDatabase) -> None:
        self.converters: dict[str, list[Converter]] = {}

        self._database = database
        self._unsuccessful_collections: dict[str, DocumentCollection[BaseDocument]] = {}

    @override
    async def get_converters(
        self,
        collection_name: str,
        from_version: Version.String,
    ) -> Sequence[Converter]:
        if collection_name not in self.converters:
            []

        converters = self.converters[collection_name]

        for i, converter in enumerate(converters):
            if converter.from_version == from_version:
                return converters[i:]

        raise ValueError(f"No converters found starting from version {from_version}.")


class DocumentConverterService:
    def __init__(
        self, logger: Logger, database: DocumentDatabase, registry: ConverterRegistry
    ) -> None:
        self._logger = logger
        self._database = database
        self._registry = registry

    async def _populate_unsuccessful_entities(
        self,
        collection_name: str,
        unsuccessful_entities: Sequence[BaseDocument],
        schema: type[BaseDocument],
    ) -> None:
        unsuccessful_collection = await self._database.get_or_create_collection(
            f"unsuccessful_{collection_name}",
            schema=schema,
        )

        for entity in unsuccessful_entities:
            await unsuccessful_collection.insert_one(entity)

    async def convert(
        self,
        collection_name: str,
        entities: Sequence[BaseDocument],
        schema: type[BaseDocument],
    ) -> Sequence[BaseDocument]:
        if not entities:
            self._logger.info(f"No entities to convert for collection '{collection_name}'.")
            return []

        # Assume all entities share the same starting version
        from_version = entities[0]["version"]
        self._logger.info(
            f"Starting conversion for collection '{collection_name}' "
            f"from version {from_version}."
        )

        converters = await self._registry.get_converters(collection_name, from_version)

        unsuccessful_entities = []
        for converter in converters:
            new_entities = []
            for entity in entities:
                try:
                    new_entities.append(await converter.convert(entity))
                except Exception as e:
                    self._logger.warning(f"Failed to convert entity {entity['id']}: {e}")
                    unsuccessful_entities.append(entity)
            entities = new_entities

        if unsuccessful_entities:
            self._logger.warning(
                f"{len(unsuccessful_entities)} entities failed to convert "
                f"for collection '{collection_name}'."
            )
            await self._populate_unsuccessful_entities(
                collection_name, unsuccessful_entities, schema
            )

        self._logger.info(
            f"Successfully converted {len(entities)} entities for collection '{collection_name}'."
        )

        return entities
