from collections.abc import Mapping
from typing import Any, cast
from sentence_transformers import SentenceTransformer

from emcie.server.core.nlp.common import EstimatingTokenizer
from emcie.server.core.nlp.embedding import Embedder, EmbeddingResult


class SBertEstimatingTokenizer(EstimatingTokenizer):
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

    async def tokenize(self, prompt: str) -> list[int]:
        return cast(list[int], self._model.tokenizer.encode(prompt, add_special_tokens=False))

    async def estimate_token_count(self, prompt: str) -> int:
        tokens = self._model.tokenizer.encode(prompt, add_special_tokens=False)
        return len(tokens)


class SBertEmbedder(Embedder):
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._client = SentenceTransformer(model_name)

    async def embed(
        self,
        texts: list[str],
        hints: Mapping[str, Any] = {},
    ) -> EmbeddingResult:
        embeddings = self._client.encode(texts)

        return EmbeddingResult(vectors=list(embeddings))


class SBertAllMiniLML6V2(SBertEmbedder):
    def __init__(self) -> None:
        super().__init__(model_name="all-MiniLM-L6-v2")

        self._estimating_tokenizer = SBertEstimatingTokenizer(self.model_name)

    @property
    def id(self) -> str:
        return f"openai/{self.model_name}"

    @property
    def max_tokens(self) -> int:
        return 128000

    def get_tokenizer(self) -> SBertEstimatingTokenizer:
        return self._estimating_tokenizer
