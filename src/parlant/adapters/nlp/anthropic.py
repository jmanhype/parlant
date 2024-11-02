import time
from pydantic import ValidationError
from anthropic import AsyncAnthropic  # type: ignore
from typing import Any, Mapping
import jsonfinder  # type: ignore
import os

from parlant.adapters.nlp.sbert import SBertAllMiniLML6V2
from parlant.core.nlp.embedding import Embedder
from parlant.core.nlp.generation import T, BaseSchematicGenerator, GenerationInfo, SchematicGenerationResult, TokenEstimator
from parlant.core.logging import Logger
from parlant.core.nlp.moderation import ModerationService, NoModeration
from parlant.core.nlp.service import NLPService


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

        self._estimating_tokenizer = AnthropicEstimatingTokenizer(model_name=self.model_name)

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
                    schema_name=self.schema.__name__, model=self.id, duration=(t_end - t_start)
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
    def __init__(
        self,
        logger: Logger,
    ) -> None:
        self._logger = logger

    async def get_schematic_generator(self, t: type[T]) -> AnthropicAISchematicGenerator[T]:
        return Claude_Sonnet_3_5[T](self._logger)

    async def get_embedder(self) -> Embedder:
        return SBertAllMiniLML6V2()

    async def get_moderation_service(self) -> ModerationService:
        return NoModeration()
