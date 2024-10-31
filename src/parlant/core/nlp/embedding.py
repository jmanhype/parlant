from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from lagom import Container
from typing import Any, Sequence

from emcie.server.core.nlp.generation import TokenEstimator


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: Sequence[Sequence[float]]


class Embedder(ABC):
    @abstractmethod
    async def embed(
        self,
        texts: list[str],
        hints: Mapping[str, Any] = {},
    ) -> EmbeddingResult:
        pass

    @abstractmethod
    @property
    def id(self) -> str: ...

    @abstractmethod
    @property
    def token_estimator(self) -> TokenEstimator: ...

    @abstractmethod
    @property
    def max_tokens(self) -> int: ...


class EmbedderFactory:
    def __init__(self, container: Container):
        self._container = container

    def create_embedder(self, embedder_type: type[Embedder]) -> Embedder:
        return self._container[embedder_type]
