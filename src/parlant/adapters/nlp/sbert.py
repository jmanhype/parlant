from collections.abc import Mapping
from typing import Any
from sentence_transformers import SentenceTransformer

from emcie.server.core.nlp.embedding import Embedder, EmbeddingResult
from emcie.server.core.nlp.generation import TokenEstimator


class SBertTokenEstimator(TokenEstimator):
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

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

    @property
    def id(self) -> str:
        return f"openai/{self.model_name}"

    @property
    def token_estimator(self) -> TokenEstimator:
        return SBertTokenEstimator(self.model_name)

    @property
    def max_tokens(self) -> int:
        return 128000
