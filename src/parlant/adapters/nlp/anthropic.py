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
from anthropic import (
    APIConnectionError,
    APIResponseValidationError,
    APITimeoutError,
    AsyncAnthropic,
    InternalServerError,
    RateLimitError,
)  # type: ignore
from typing import Any, Mapping
from typing_extensions import override
import jsonfinder  # type: ignore
import os
import tiktoken

from parlant.adapters.nlp.common import normalize_json_output
from parlant.adapters.nlp.hugging_face import JinaAIEmbedder
from parlant.core.nlp.embedding import Embedder
from parlant.core.nlp.generation import (
    T,
    GenerationInfo,
    SchematicGenerationResult,
    SchematicGenerator,
    UsageInfo,
)
from parlant.core.logging import Logger
from parlant.core.nlp.moderation import ModerationService, NoModeration
from parlant.core.nlp.policies import policy, retry
from parlant.core.nlp.service import NLPService
from parlant.core.nlp.tokenization import EstimatingTokenizer


class AnthropicEstimatingTokenizer(EstimatingTokenizer):
    def __init__(self, client: AsyncAnthropic) -> None:
        self.encoding = tiktoken.encoding_for_model("gpt-4o-2024-08-06")
        self._client = client

    @override
    async def estimate_token_count(self, prompt: str) -> int:
        return await self._client.count_tokens(prompt)


class AnthropicAISchematicGenerator(SchematicGenerator[T]):
    supported_hints = ["temperature"]

    def __init__(
        self,
        model_name: str,
        logger: Logger,
    ) -> None:
        self.model_name = model_name
        self._logger = logger

        self._client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        self._estimating_tokenizer = AnthropicEstimatingTokenizer(self._client)

    @property
    @override
    def id(self) -> str:
        return f"anthropic/{self.model_name}"

    @property
    @override
    def tokenizer(self) -> AnthropicEstimatingTokenizer:
        return self._estimating_tokenizer

    @policy(
        [
            retry(
                exceptions=(
                    APIConnectionError,
                    APITimeoutError,
                    RateLimitError,
                    APIResponseValidationError,
                )
            ),
            retry(InternalServerError, max_attempts=2, wait_times=(1.0, 5.0)),
        ]
    )
    @override
    async def generate(
        self,
        prompt: str,
        hints: Mapping[str, Any] = {},
    ) -> SchematicGenerationResult[T]:
        anthropic_api_arguments = {k: v for k, v in hints.items() if k in self.supported_hints}

        t_start = time.time()
        response = await self._client.messages.create(
            messages=[{"role": "user", "content": prompt}],
            model=self.model_name,
            max_tokens=4096,
            **anthropic_api_arguments,
        )
        t_end = time.time()

        raw_content = response.content[0].text

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
                        input_tokens=response.usage.input_tokens,
                        output_tokens=response.usage.output_tokens,
                    ),
                ),
            )
        except ValidationError:
            self._logger.error(
                f"JSON content returned by {self.model_name} does not match expected schema:\n{raw_content}"
            )
            raise


class Claude_Sonnet_3_5(AnthropicAISchematicGenerator[T]):
    def __init__(self, logger: Logger) -> None:
        super().__init__(
            model_name="claude-3-5-sonnet-20241022",
            logger=logger,
        )

    @override
    @property
    def max_tokens(self) -> int:
        return 200 * 1024


class AnthropicService(NLPService):
    def __init__(self, logger: Logger) -> None:
        self._logger = logger
        self._logger.info("Initialized AnthropicService")

    @override
    async def get_schematic_generator(self, t: type[T]) -> AnthropicAISchematicGenerator[T]:
        return Claude_Sonnet_3_5[t](self._logger)  # type: ignore

    @override
    async def get_embedder(self) -> Embedder:
        return JinaAIEmbedder()

    @override
    async def get_moderation_service(self) -> ModerationService:
        return NoModeration()
