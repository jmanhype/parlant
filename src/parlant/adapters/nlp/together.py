import time
from pydantic import ValidationError
from together import AsyncTogether  # type: ignore
from typing import Any, Mapping
import jsonfinder  # type: ignore
import os
import tiktoken

from parlant.core.engines.alpha.message_event_generator import MessageEventSchema
from parlant.core.nlp.embedding import Embedder, EmbeddingResult
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


class LlamaEstimatingTokenizer(Tokenizer):
    def __init__(self) -> None:
        self.encoding = tiktoken.encoding_for_model("gpt-4o-2024-08-06")

    async def tokenize(self, prompt: str) -> list[int]:
        return self.encoding.encode(prompt)

    async def estimate_token_count(self, prompt: str) -> int:
        tokens = self.encoding.encode(prompt)
        return len(tokens) + 36


class TogetherAISchematicGenerator(BaseSchematicGenerator[T]):
    supported_hints = ["temperature"]

    def __init__(
        self,
        model_name: str,
        logger: Logger,
    ) -> None:
        self.model_name = model_name
        self._logger = logger
        self._client = AsyncTogether(api_key=os.environ.get("TOGETHER_API_KEY"))

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
            json_start = max(0, raw_content.find("```json"))

            if json_start != -1:
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
    def id(self) -> str:
        return self.model_name

    @property
    def max_tokens(self) -> int:
        return 128000

    def get_tokenizer(self) -> LlamaEstimatingTokenizer:
        return self._estimating_tokenizer


class Llama3_1_70B(TogetherAISchematicGenerator[T]):
    def __init__(self, logger: Logger) -> None:
        super().__init__(
            model_name="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
            logger=logger,
        )

        self._estimating_tokenizer = LlamaEstimatingTokenizer()

    @property
    def id(self) -> str:
        return self.model_name

    def get_tokenizer(self) -> LlamaEstimatingTokenizer:
        return self._estimating_tokenizer

    @property
    def max_tokens(self) -> int:
        return 128000


class Llama3_1_405B(TogetherAISchematicGenerator[T]):
    def __init__(self, logger: Logger) -> None:
        super().__init__(
            model_name="meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
            logger=logger,
        )

        self._estimating_tokenizer = LlamaEstimatingTokenizer()

    @property
    def id(self) -> str:
        return self.model_name

    def get_tokenizer(self) -> LlamaEstimatingTokenizer:
        return self._estimating_tokenizer

    @property
    def max_tokens(self) -> int:
        return 128000


class TogetherAIEmbedder(Embedder):
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._client = AsyncTogether(api_key=os.environ.get("TOGETHER_API_KEY"))

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


class M2Bert32KEstimatingTokenizer(Tokenizer):
    def __init__(self) -> None:
        self.encoding = tiktoken.encoding_for_model("gpt-4o-2024-08-06")

    async def tokenize(self, prompt: str) -> list[int]:
        return self.encoding.encode(prompt)

    async def estimate_token_count(self, prompt: str) -> int:
        tokens = self.encoding.encode(prompt)
        return len(tokens)


class M2Bert32K(TogetherAIEmbedder):
    def __init__(self) -> None:
        super().__init__(model_name="togethercomputer/m2-bert-80M-32k-retrieval")
        self._estimating_tokenizer = M2Bert32KEstimatingTokenizer()

    @property
    def id(self) -> str:
        return self.model_name

    @property
    def max_tokens(self) -> int:
        return 32768

    def get_tokenizer(self) -> M2Bert32KEstimatingTokenizer:
        return self._estimating_tokenizer


class TogetherService(NLPService):
    def __init__(
        self,
        logger: Logger,
    ) -> None:
        self._logger = logger

    async def get_schematic_generator(self, t: type[T]) -> TogetherAISchematicGenerator[T]:
        if t == MessageEventSchema:
            return Llama3_1_405B[t](self._logger)  # type: ignore
        return Llama3_1_70B[t](self._logger)  # type: ignore

    async def get_fallback_schematic_generator(self, t: type[T]) -> FallbackSchematicGenerator[T]:
        return FallbackSchematicGenerator(
            Llama3_1_8B[t](self._logger),  # type: ignore
            Llama3_1_70B[t](self._logger),  # type: ignore
            logger=self._logger,
        )

    async def get_embedder(self) -> Embedder:
        return M2Bert32K()

    async def get_moderation_service(self) -> ModerationService:
        return NoModeration()
