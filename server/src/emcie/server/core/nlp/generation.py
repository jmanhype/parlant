from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Generic, Mapping, TypeVar, cast, get_args

from emcie.server.core.common import DefaultBaseModel
from emcie.server.core.logging import Logger

T = TypeVar("T", bound=DefaultBaseModel)


@dataclass(frozen=True)
class SchematicGenerationResult(Generic[T]):
    content: T


class SchematicGenerator(ABC, Generic[T]):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        hints: Mapping[str, Any] = {},
    ) -> SchematicGenerationResult[T]: ...


class BaseSchematicGenerator(SchematicGenerator[T]):
    @cached_property
    def schema(self) -> type[T]:
        orig_class = getattr(self, "__orig_class__")
        generic_args = get_args(orig_class)
        return cast(type[T], generic_args[0])


class FallbackSchematicGenerator(SchematicGenerator[T]):
    def __init__(
        self,
        *generators: SchematicGenerator[T],
        logger: Logger,
    ) -> None:
        self._generators = generators
        self._logger = logger

    async def generate(
        self,
        prompt: str,
        hints: Mapping[str, Any] = {},
    ) -> SchematicGenerationResult[T]:
        last_exception: Exception
        total_generators = len(self._generators)

        for index, generator in enumerate(self._generators):
            generator_name = type(generator).__name__
            try:
                result = await generator.generate(prompt, hints)
                return result
            except Exception as e:
                self._logger.warning(
                    f"Generator {index + 1}/{total_generators} failed: {generator_name} with error: {e}"
                )
                last_exception = e
                continue

        raise last_exception
