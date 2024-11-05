from pathlib import Path
import time
from pydantic import ValidationError
from anthropic import AsyncAnthropic  # type: ignore
from typing import Any, Mapping
import jsonfinder  # type: ignore
import os
import tiktoken

from parlant.adapters.nlp.hugging_face import JinaAIEmbedder
from parlant.core.nlp.embedding import Embedder
from parlant.core.nlp.generation import (
    T,
    BaseSchematicGenerator,
    FallbackSchematicGenerator,
    GenerationInfo,
    SchematicGenerationResult,
    UsageInfo,
)
from parlant.core.logging import Logger
from parlant.core.nlp.moderation import ModerationService, NoModeration
from parlant.core.nlp.service import NLPService
from parlant.core.nlp.tokenizer import Tokenizer


class AnthropicEstimatingTokenizer(Tokenizer):
    def __init__(self) -> None:
        self.encoding = tiktoken.encoding_for_model("gpt-4o-2024-08-06")

    async def tokenize(self, prompt: str) -> list[int]:
        return self.encoding.encode(prompt)

    async def estimate_token_count(self, prompt: str) -> int:
        tokens = self.encoding.encode(prompt)
        return len(tokens)


class AnthropicAISchematicGenerator(BaseSchematicGenerator[T]):
    supported_hints = ["temperature"]

    def __init__(
        self,
        model_name: str,
        logger: Logger,
    ) -> None:
        self.model_name = model_name
        self._logger = logger

        self._client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        self._estimating_tokenizer = AnthropicEstimatingTokenizer()

    @property
    def id(self) -> str:
        return f"anthropic/{self.model_name}"

    def get_tokenizer(self) -> AnthropicEstimatingTokenizer:
        return self._estimating_tokenizer

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
            max_tokens=2048,
            **anthropic_api_arguments,
        )
        t_end = time.time()

        raw_content = response.content[0].text

        try:
            if json_start := max(0, raw_content.find("```json")):
                json_start = json_start + 7

            json_end = raw_content[json_start:].find("```")

            if json_end == -1:
                json_end = len(raw_content[json_start:])

            json_content = raw_content[json_start : json_start + json_end]
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
                    usage_info=UsageInfo(
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

    @property
    def max_tokens(self) -> int:
        return 200000


class AnthropicService(NLPService):
    def __init__(self, logger: Logger, dir_path: Path) -> None:
        self._logger = logger
        self._dir_path = dir_path

    async def get_schematic_generator(self, t: type[T]) -> AnthropicAISchematicGenerator[T]:
        return Claude_Sonnet_3_5[t](self._logger)  # type: ignore

    async def get_fallback_schematic_generator(self, t: type[T]) -> FallbackSchematicGenerator[T]:
        return FallbackSchematicGenerator(Claude_Sonnet_3_5[t](self._logger), logger=self._logger)  # type: ignore

    async def get_embedder(self) -> Embedder:
        return JinaAIEmbedder(self._dir_path)

    async def get_moderation_service(self) -> ModerationService:
        return NoModeration()
