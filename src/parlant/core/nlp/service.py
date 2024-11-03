from abc import ABC, abstractmethod

from parlant.core.nlp.embedding import Embedder
from parlant.core.nlp.generation import T, FallbackSchematicGenerator, SchematicGenerator
from parlant.core.nlp.moderation import ModerationService


class NLPService(ABC):
    @abstractmethod
    async def get_schematic_generator(self, t: type[T]) -> SchematicGenerator[T]: ...

    @abstractmethod
    async def get_fallback_schematic_generator(
        self, t: type[T]
    ) -> FallbackSchematicGenerator[T]: ...

    @abstractmethod
    async def get_embedder(self) -> Embedder: ...

    @abstractmethod
    async def get_moderation_service(self) -> ModerationService: ...
