from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Generic, Mapping, TypeVar, cast, get_args

from parlant.core.common import DefaultBaseModel
from parlant.core.logging import Logger

T = TypeVar("T", bound=DefaultBaseModel)


class TokenEstimator(ABC):
    @abstractmethod
    async def estimate_token_count(self, prompt: str) -> int: ...


@dataclass(frozen=True)
class SchematicGenerationResult(Generic[T]):
    content: T
    # duration


class SchematicGenerator(ABC, Generic[T]):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        hints: Mapping[str, Any] = {},
    ) -> SchematicGenerationResult[T]: ...

    @abstractmethod
    @property
    def id(self) -> str: ...

    @abstractmethod
    @property
    def token_estimator(self) -> TokenEstimator: ...

    @abstractmethod
    @property
    def max_tokens(self) -> int: ...


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
        assert generators, "Fallback generator must be instantiated with at least 1 generator"

        self._generators = generators
        self._logger = logger

    async def generate(
        self,
        prompt: str,
        hints: Mapping[str, Any] = {},
    ) -> SchematicGenerationResult[T]:
        last_exception: Exception

        for index, generator in enumerate(self._generators):
            try:
                result = await generator.generate(prompt=prompt, hints=hints)
                return result
            except Exception as e:
                self._logger.warning(
                    f"Generator {index + 1}/{len(self._generators)} failed: {type(generator).__name__}: {e}"
                )
                last_exception = e

        raise last_exception

    @property
    def id(self) -> str:
        return self._generators[0].id

    @property
    def token_estimator(self) -> TokenEstimator:
        return self._generators[0].token_estimator

    @property
    def max_tokens(self) -> int:
        return self._generators[0].max_tokens
