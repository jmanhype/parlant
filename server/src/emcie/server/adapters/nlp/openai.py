from openai import AsyncClient
from typing import Any, Mapping
import json
import jsonfinder  # type: ignore
import os

from pydantic import ValidationError

from emcie.server.core.nlp.embedding import Embedder, EmbeddingResult
from emcie.server.core.nlp.generation import T, BaseSchematicGenerator, SchematicGenerationResult
from emcie.server.core.logger import Logger


class OpenAISchematicGenerator(BaseSchematicGenerator[T]):
    supported_openai_params = ["temperature", "logit_bias", "max_tokens"]
    supported_hints = supported_openai_params + ["strict"]

    def __init__(
        self,
        model_name: str,
        logger: Logger,
    ) -> None:
        self.model_name = model_name
        self._logger = logger
        self._client = AsyncClient(api_key=os.environ["OPENAI_API_KEY"])

    async def generate(
        self,
        prompt: str,
        hints: Mapping[str, Any] = {},
    ) -> SchematicGenerationResult[T]:
        openai_api_arguments = {k: v for k, v in hints.items() if k in self.supported_openai_params}

        if hints.get("strict", False):
            response = await self._client.beta.chat.completions.parse(
                messages=[{"role": "user", "content": prompt}],
                model=self.model_name,
                response_format=self.schema,
                **openai_api_arguments,
            )

            parsed_object = response.choices[0].message.parsed
            assert parsed_object

            return SchematicGenerationResult[T](content=parsed_object)

        else:
            response = await self._client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model_name,
                response_format={"type": "json_object"},
                **openai_api_arguments,
            )

            raw_content = response.choices[0].message.content or "{}"

            try:
                json_content = json.loads(raw_content)
            except json.JSONDecodeError:
                self._logger.warning(f"Invalid JSON returned by {self.model_name}:\n{raw_content}")
                json_content = jsonfinder.only_json(raw_content)[2]
                self._logger.warning("Found JSON content within model response; continuing...")

            try:
                content = self.schema.model_validate(json_content)
                return SchematicGenerationResult(content=content)
            except ValidationError:
                self._logger.error(
                    f"JSON content returned by {self.model_name} does not match expected schema:\n{raw_content}"
                )
                raise


class GPT_4o(OpenAISchematicGenerator[T]):
    def __init__(self, logger: Logger) -> None:
        super().__init__(model_name="gpt-4o-2024-08-06", logger=logger)


class GPT_4o_Mini(OpenAISchematicGenerator[T]):
    def __init__(self, logger: Logger) -> None:
        super().__init__(model_name="gpt-4o-mini", logger=logger)


class OpenAIEmbedder(Embedder):
    supported_arguments = ["dimensions"]

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._client = AsyncClient(api_key=os.environ["OPENAI_API_KEY"])

    async def embed(
        self,
        texts: list[str],
        hints: Mapping[str, Any] = {},
    ) -> EmbeddingResult:
        filtered_hints = {k: v for k, v in hints.items() if k in self.supported_arguments}

        response = await self._client.embeddings.create(
            model=self.model_name,
            input=texts,
            **filtered_hints,
        )

        vectors = [data_point.embedding for data_point in response.data]
        return EmbeddingResult(vectors=vectors)


class OpenAITextEmbedding3Large(OpenAIEmbedder):
    def __init__(self) -> None:
        super().__init__(model_name="text-embedding-3-large")


class OpenAITextEmbedding3Small(OpenAIEmbedder):
    def __init__(self) -> None:
        super().__init__(model_name="text-embedding-3-small")
