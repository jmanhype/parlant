from abc import ABC, abstractmethod
from typing import (
    Any,
    Awaitable,
    Callable,
    Generic,
    NamedTuple,
    Sequence,
    TypeVar,
    cast,
    get_type_hints,
)
from typing_extensions import override

from parlant.core.common import Version
from parlant.core.logging import Logger
from parlant.core.nlp.embedding import Embedder
from parlant.core.persistence.common import ensure_is_total
from parlant.core.persistence.document_database import (
    BaseDocument,
    DocumentCollection,
    DocumentDatabase,
)
from parlant.core.persistence.vector_database import (
    BaseDocument as VectorBaseDocument,
    VectorDatabase,
)


TInputDocument = TypeVar("TInputDocument", bound=BaseDocument)
TOutputDocument = TypeVar("TOutputDocument", bound=BaseDocument)


class DocumentConverter(ABC, Generic[TInputDocument, TOutputDocument]):
    @property
    @abstractmethod
    def input_schema(self) -> type[TInputDocument]: ...

    @property
    @abstractmethod
    def output_schema(self) -> type[TOutputDocument]: ...

    async def convert(self, entity: TInputDocument) -> TOutputDocument:
        ensure_is_total(entity, self.input_schema)
        result = await self.do_conversion(entity)
        ensure_is_total(result, self.output_schema)
        return result

    @abstractmethod
    async def do_conversion(self, entity: TInputDocument) -> TOutputDocument: ...


def conversion(
    fn: Callable[[TInputDocument], Awaitable[TOutputDocument]],
) -> DocumentConverter[TInputDocument, TOutputDocument]:
    """
    Decorates an async function of signature (entity: TInputDocument) -> TOutputDocument
    and returns a DocumentConverter[TInputDocument, TOutputDocument] object that:

        1) Ensures 'entity' matches TInputDocument.
        2) Calls the function.
        3) Ensures the result matches TOutputDocument.

    We rely on function annotations to infer TInputDocument and TOutputDocument.
    """
    hints = get_type_hints(fn)
    _, in_type = next((name, tp) for name, tp in hints.items() if name != "return")
    out_type = hints["return"]

    class _DynamicConverter(DocumentConverter[TInputDocument, TOutputDocument]):
        @property
        def input_schema(self) -> type[TInputDocument]:
            return cast(type[TInputDocument], in_type)

        @property
        def output_schema(self) -> type[TOutputDocument]:
            return cast(type[TOutputDocument], out_type)

        async def do_conversion(self, entity: TInputDocument) -> TOutputDocument:
            return await fn(entity)

    return _DynamicConverter()


TInputVectorDocument = TypeVar("TInputVectorDocument", bound=VectorBaseDocument)
TOutputVectorDocument = TypeVar("TOutputVectorDocument", bound=VectorBaseDocument)


class VectorConverter(ABC, Generic[TInputVectorDocument, TOutputVectorDocument]):
    @property
    @abstractmethod
    def input_schema(self) -> type[TInputVectorDocument]: ...

    @property
    @abstractmethod
    def output_schema(self) -> type[TOutputVectorDocument]: ...

    async def convert(self, entity: TInputVectorDocument) -> TOutputVectorDocument:
        ensure_is_total(entity, self.input_schema)
        result = await self.do_conversion(entity)
        ensure_is_total(result, self.output_schema)
        return result

    @abstractmethod
    async def do_conversion(self, entity: TInputVectorDocument) -> TOutputVectorDocument: ...


def vector_conversion(
    fn: Callable[[TInputVectorDocument], Awaitable[TOutputVectorDocument]],
) -> VectorConverter[TInputVectorDocument, TOutputVectorDocument]:
    """
    Decorates an async function of signature (entity: TInputVectorDocument) -> TOutputVectorDocument
    and returns a VectorConverter[TInputVectorDocument, TOutputVectorDocument] object that:

        1) Ensures 'entity' matches TInputVectorDocument.
        2) Calls the function.
        3) Ensures the result matches TOutputVectorDocument.

    We rely on function annotations to infer TInputVectorDocument and TOutputVectorDocument.
    """
    hints = get_type_hints(fn)
    _, in_type = next((name, tp) for name, tp in hints.items() if name != "return")
    out_type = hints["return"]

    class _DynamicVectorConverter(VectorConverter[TInputVectorDocument, TOutputVectorDocument]):
        @property
        def input_schema(self) -> type[TInputVectorDocument]:
            return cast(type[TInputVectorDocument], in_type)

        @property
        def output_schema(self) -> type[TOutputVectorDocument]:
            return cast(type[TOutputVectorDocument], out_type)

        async def do_conversion(self, entity: TInputVectorDocument) -> TOutputVectorDocument:
            return await fn(entity)

    return _DynamicVectorConverter()


class DocumentConverterRegistryBase(ABC):
    @abstractmethod
    async def get_converters(
        self,
        collection_name: str,
        input_schema: type[BaseDocument],
    ) -> Sequence[DocumentConverter[BaseDocument, BaseDocument]]: ...


class VectorConverterRegistryBase(ABC):
    @abstractmethod
    async def get_converters(
        self,
        collection_name: str,
        input_schema: type[VectorBaseDocument],
    ) -> Sequence[VectorConverter[VectorBaseDocument, VectorBaseDocument]]: ...


class DocumentConverterRegistry(DocumentConverterRegistryBase):
    def __init__(self) -> None:
        self.converters: dict[str, list[DocumentConverter[Any, Any]]] = {}

        self._unsuccessful_collections: dict[str, DocumentCollection[BaseDocument]] = {}

    @override
    async def get_converters(
        self,
        collection_name: str,
        input_schema: type[BaseDocument],
    ) -> Sequence[DocumentConverter[BaseDocument, BaseDocument]]:
        if collection_name not in self.converters:
            return []

        converters = self.converters[collection_name]
        for i, converter in enumerate(converters):
            if converter.input_schema == input_schema:
                return converters[i:]

        raise ValueError(f"No converters found starting from schema {input_schema.__name__}.")


class VectorConverterRegistry(VectorConverterRegistryBase):
    def __init__(self) -> None:
        self.converters: dict[str, list[VectorConverter[Any, Any]]] = {}

    @override
    async def get_converters(
        self,
        collection_name: str,
        input_schema: type[VectorBaseDocument],
    ) -> Sequence[VectorConverter[VectorBaseDocument, VectorBaseDocument]]:
        if collection_name not in self.converters:
            return []

        converters = self.converters[collection_name]
        for i, converter in enumerate(converters):
            if converter.input_schema == input_schema:
                return converters[i:]

        raise ValueError(
            f"No vector-converters found starting from schema {input_schema.__name__}."
        )


class ConversionResult(NamedTuple):
    schema: type[BaseDocument]
    entities: Sequence[BaseDocument]


class DocumentConverterService:
    def __init__(
        self,
        logger: Logger,
        registry: DocumentConverterRegistry,
    ) -> None:
        self._logger = logger
        self._registry = registry

    async def _populate_unsuccessful_entities(
        self,
        database: DocumentDatabase,
        collection_name: str,
        unsuccessful_entities: Sequence[BaseDocument],
        schema: type[BaseDocument],
    ) -> None:
        unsuccessful_coll_name = f"unsuccessful_{collection_name}_{schema.__name__}"

        self._logger.warning(
            f"Populating {len(unsuccessful_entities)} unsuccessful "
            f"entities into collection '{unsuccessful_coll_name}' "
            f"(schema={schema.__name__})."
        )

        unsuccessful_collection = await database.get_or_create_collection(
            unsuccessful_coll_name,
            schema=schema,
        )

        for entity in unsuccessful_entities:
            await unsuccessful_collection.insert_one(entity)

    async def convert(
        self,
        database: DocumentDatabase,
        collection_name: str,
        input_schema: type[TInputDocument],
        input_entities: Sequence[TInputDocument],
        from_version: Version.String | None = None,
    ) -> ConversionResult:
        converters = await self._registry.get_converters(collection_name, input_schema)

        if not converters:
            self._logger.info(
                f"No converters found for '{collection_name}' from version '{from_version}'."
            )
            return ConversionResult(schema=input_schema, entities=input_entities)

        if not input_entities:
            self._logger.info(
                f"No entities to convert; final schema is {converters[-1].output_schema} "
                f"after applying {len(converters)} converter(s)."
            )
            return ConversionResult(schema=converters[-1].output_schema, entities=[])

        entities: list[BaseDocument] = list(input_entities)
        current_schema: type[BaseDocument] = input_schema

        for converter in converters:
            new_entities = []
            unsuccessful_entities = []

            self._logger.debug(
                f"Applying converter: from_schema={converter.input_schema.__name__}, "
                f"to_schema={converter.output_schema.__name__}, "
            )

            for entity in entities:
                try:
                    converted: BaseDocument = await converter.convert(entity)
                    new_entities.append(converted)
                except Exception as e:
                    self._logger.warning(f"Failed converting entity {entity['id']}: {e}")
                    unsuccessful_entities.append(entity)

            if unsuccessful_entities:
                await self._populate_unsuccessful_entities(
                    database=database,
                    collection_name=collection_name,
                    unsuccessful_entities=unsuccessful_entities,
                    schema=converter.input_schema,
                )

            entities = new_entities
            current_schema = converter.output_schema

        self._logger.info(
            f"Successfully converted {len(entities)} entities for '{collection_name}'."
        )
        return ConversionResult(schema=current_schema, entities=entities)


class VectorConverterService:
    def __init__(
        self,
        logger: Logger,
        registry: VectorConverterRegistry,
    ) -> None:
        self._logger = logger
        self._registry = registry

    async def _populate_unsuccessful_entities(
        self,
        database: VectorDatabase,
        embedder_type: type[Embedder],
        collection_name: str,
        unsuccessful_entities: Sequence[VectorBaseDocument],
        schema: type[VectorBaseDocument],
    ) -> None:
        """
        Save unsuccessful conversions into a separate database collection.
        """
        unsuccessful_collection_name = f"unsuccessful_{collection_name}_{schema.__name__}"
        self._logger.warning(
            f"Populating {len(unsuccessful_entities)} unsuccessful vector entities "
            f"into collection '{unsuccessful_collection_name}' (schema={schema.__name__})."
        )
        unsuccessful_collection = await database.get_or_create_collection(
            unsuccessful_collection_name, schema, embedder_type
        )
        for entity in unsuccessful_entities:
            await unsuccessful_collection.insert_one(entity)

    async def convert(
        self,
        database: VectorDatabase,
        embedder_type: type[Embedder],
        collection_name: str,
        input_schema: type[VectorBaseDocument],
        input_entities: Sequence[VectorBaseDocument],
        from_version: Version.String | None = None,
    ) -> ConversionResult:
        """
        Convert entities from one version to the next using registered converters.
        """
        converters = await self._registry.get_converters(collection_name, input_schema)

        if not converters:
            self._logger.info(
                f"No converters found for '{collection_name}' starting from version '{from_version}'."
            )
            return ConversionResult(schema=input_schema, entities=input_entities)

        if not input_entities:
            self._logger.info(
                f"No entities to convert. Final schema is {converters[-1].output_schema} "
                f"after applying {len(converters)} converters."
            )
            return ConversionResult(schema=converters[-1].output_schema, entities=[])

        entities: list[VectorBaseDocument] = list(input_entities)
        current_schema = input_schema

        for converter in converters:
            new_entities = []
            unsuccessful_entities = []

            self._logger.debug(
                f"Applying converter: from_schema={converter.input_schema.__name__}, "
                f"to_schema={converter.output_schema.__name__}."
            )

            for entity in entities:
                try:
                    converted = await converter.convert(entity)
                    new_entities.append(converted)
                except Exception as e:
                    self._logger.warning(f"Failed converting vector entity {entity['id']}: {e}")
                    unsuccessful_entities.append(entity)

            if unsuccessful_entities:
                await self._populate_unsuccessful_entities(
                    database=database,
                    embedder_type=embedder_type,
                    collection_name=collection_name,
                    unsuccessful_entities=unsuccessful_entities,
                    schema=converter.input_schema,
                )

            entities = new_entities
            current_schema = converter.output_schema

        self._logger.info(
            f"Successfully converted {len(entities)} vector entities for '{collection_name}'."
        )
        return ConversionResult(schema=current_schema, entities=entities)
