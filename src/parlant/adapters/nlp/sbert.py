from collections.abc import Mapping
from typing import Any
from sentence_transformers import SentenceTransformer
from emcie.server.core.nlp.embedding import Embedder, EmbeddingResult


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
