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

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from lagom import Container
from typing import Any, Sequence

from parlant.core.nlp.tokenization import EstimatingTokenizer


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

    @property
    @abstractmethod
    def id(self) -> str: ...

    @property
    @abstractmethod
    def max_tokens(self) -> int: ...

    @property
    @abstractmethod
    def tokenizer(self) -> EstimatingTokenizer: ...


class EmbedderFactory:
    def __init__(self, container: Container):
        self._container = container

    def create_embedder(self, embedder_type: type[Embedder]) -> Embedder:
        return self._container[embedder_type]
