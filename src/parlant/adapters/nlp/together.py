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

import time
from pydantic import ValidationError
from together import AsyncTogether  # type: ignore
from together.error import (  # type: ignore
    RateLimitError,
    Timeout,
    APIConnectionError,
    APIError,
    ServiceUnavailableError,
)
from typing import Any, Mapping
from typing_extensions import override
import jsonfinder  # type: ignore
import os
import tiktoken

from parlant.adapters.nlp.common import normalize_json_output
from parlant.adapters.nlp.hugging_face import HuggingFaceEstimatingTokenizer
from parlant.core.engines.alpha.fluid_message_generator import FluidMessageSchema
from parlant.core.engines.alpha.tool_caller import ToolCallInferenceSchema
from parlant.core.nlp.embedding import Embedder, EmbeddingResult
from parlant.core.nlp.generation import (
    T,
    SchematicGenerator,
    FallbackSchematicGenerator,
    GenerationInfo,
    SchematicGenerationResult,
    UsageInfo,
)
from parlant.core.logging import Logger
from parlant.core.nlp.moderation import ModerationService, NoModeration
from parlant.core.nlp.policies import policy, retry
from parlant.core.nlp.service import NLPService
from parlant.core.nlp.tokenization import EstimatingTokenizer


class LlamaEstimatingTokenizer(EstimatingTokenizer):
    def __init__(self) -> None:
        self.encoding = tiktoken.encoding_for_model("gpt-4o-2024-08-06")

    @override
    async def estimate_token_count(self, prompt: str) -> int:
        tokens = self.encoding.encode(prompt)
        return len(tokens) + 36


class TogetherAISchematicGenerator(SchematicGenerator[T]):
    supported_hints = ["temperature"]

    def __init__(
        self,
        model_name: str,
        logger: Logger,
    ) -> None:
        self.model_name = model_name
        self._logger = logger
        self._client = AsyncTogether(api_key=os.environ.get("TOGETHER_API_KEY"))

    @policy(
        [
            retry(
                exceptions=(
                    RateLimitError,
                    Timeout,
                    APIConnectionError,
                    APIError,
                )
            ),
            retry(ServiceUnavailableError, max_attempts=2, wait_times=(1.0, 5.0)),
        ]
    )
    @override
    async def generate(
        self,
        prompt: str,
        hints: Mapping[str, Any] = {},
    ) -> SchematicGenerationResult[T]:
        together_api_arguments = {k: v for k, v in hints.items() if k in self.supported_hints}

        t_start = time.time()
        response = await self._client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=self.model_name,
            response_format={"type": "json_object"},
            **together_api_arguments,
        )
        t_end = time.time()

        raw_content = response.choices[0].message.content or "{}"

        try:
            json_content = normalize_json_output(raw_content)
            json_object = jsonfinder.only_json(json_content)[2]
        except Exception:
            self._logger.error(
                f"Failed to extract JSON returned by {self.model_name}:\n{raw_content}"
            )
            raise

        try:
            model_content = self.schema.model_validate(json_object)

            return SchematicGenerationResult(
                content=model_content,
                info=GenerationInfo(
                    schema_name=self.schema.__name__,
                    model=self.id,
                    duration=(t_end - t_start),
                    usage=UsageInfo(
                        input_tokens=response.usage.prompt_tokens,
                        output_tokens=response.usage.completion_tokens,
                        extra={},
                    ),
                ),
            )
        except ValidationError:
            self._logger.error(
                f"JSON content returned by {self.model_name} does not match expected schema:\n{raw_content}"
            )
            raise


class Llama3_1_8B(TogetherAISchematicGenerator[T]):
    def __init__(self, logger: Logger) -> None:
        super().__init__(
            model_name="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
            logger=logger,
        )
        self._estimating_tokenizer = LlamaEstimatingTokenizer()

    @property
    @override
    def id(self) -> str:
        return self.model_name

    @property
    @override
    def max_tokens(self) -> int:
        return 128 * 1024

    @property
    @override
    def tokenizer(self) -> LlamaEstimatingTokenizer:
        return self._estimating_tokenizer


class Llama3_1_70B(TogetherAISchematicGenerator[T]):
    def __init__(self, logger: Logger) -> None:
        super().__init__(
            model_name="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
            logger=logger,
        )

        self._estimating_tokenizer = LlamaEstimatingTokenizer()

    @property
    @override
    def id(self) -> str:
        return self.model_name

    @property
    @override
    def tokenizer(self) -> LlamaEstimatingTokenizer:
        return self._estimating_tokenizer

    @property
    @override
    def max_tokens(self) -> int:
        return 128 * 1024


class Llama3_1_405B(TogetherAISchematicGenerator[T]):
    def __init__(self, logger: Logger) -> None:
        super().__init__(
            model_name="meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
            logger=logger,
        )

        self._estimating_tokenizer = LlamaEstimatingTokenizer()

    @property
    @override
    def id(self) -> str:
        return self.model_name

    @property
    @override
    def tokenizer(self) -> LlamaEstimatingTokenizer:
        return self._estimating_tokenizer

    @property
    @override
    def max_tokens(self) -> int:
        return 128 * 1024


class TogetherAIEmbedder(Embedder):
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._client = AsyncTogether(api_key=os.environ.get("TOGETHER_API_KEY"))

    @policy(
        [
            retry(
                exceptions=(
                    RateLimitError,
                    Timeout,
                    APIConnectionError,
                    APIError,
                )
            ),
            retry(ServiceUnavailableError, max_attempts=2, wait_times=(1.0, 5.0)),
        ]
    )
    @override
    async def embed(
        self,
        texts: list[str],
        hints: Mapping[str, Any] = {},
    ) -> EmbeddingResult:
        _ = hints

        response = await self._client.embeddings.create(
            model=self.model_name,
            input=texts,
        )

        vectors = [data_point.embedding for data_point in response.data]
        return EmbeddingResult(vectors=vectors)


class M2Bert32K(TogetherAIEmbedder):
    def __init__(self) -> None:
        super().__init__(model_name="togethercomputer/m2-bert-80M-32k-retrieval")
        self._estimating_tokenizer = HuggingFaceEstimatingTokenizer(self.model_name)

    @property
    @override
    def id(self) -> str:
        return self.model_name

    @property
    @override
    def max_tokens(self) -> int:
        return 32 * 1024

    @property
    @override
    def tokenizer(self) -> HuggingFaceEstimatingTokenizer:
        return self._estimating_tokenizer

    @property
    @override
    def dimensions(self) -> int:
        return 768


class TogetherService(NLPService):
    def __init__(
        self,
        logger: Logger,
    ) -> None:
        self._logger = logger
        self._logger.info("Initialized TogetherService")

    @override
    async def get_schematic_generator(self, t: type[T]) -> TogetherAISchematicGenerator[T]:
        if t == FluidMessageSchema:
            return Llama3_1_405B[t](self._logger)  # type: ignore
        elif t == ToolCallInferenceSchema:
            return FallbackSchematicGenerator(
                Llama3_1_8B[t](self._logger),  # type: ignore
                Llama3_1_70B[t](self._logger),  # type: ignore
                logger=self._logger,
            )
        return Llama3_1_70B[t](self._logger)  # type: ignore

    @override
    async def get_embedder(self) -> Embedder:
        return M2Bert32K()

    @override
    async def get_moderation_service(self) -> ModerationService:
        return NoModeration()
