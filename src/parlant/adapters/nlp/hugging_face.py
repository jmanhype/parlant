from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast
from transformers import AutoModel, AutoTokenizer  # type: ignore

from parlant.core.nlp.tokenizer import Tokenizer
from parlant.core.nlp.embedding import Embedder, EmbeddingResult


class HuggingFaceEmbedder(Embedder):
    def __init__(self, model_name: str, dir_path: Path) -> None:
        self.model_name = model_name
        self._model = AutoModel.from_pretrained(model_name)
        self._model.save_pretrained(dir_path)

    async def embed(
        self,
        texts: list[str],
        hints: Mapping[str, Any] = {},
    ) -> EmbeddingResult:
        embeddings = self._model.encode(texts)

        return EmbeddingResult(vectors=list(embeddings))


class AutoTokenizerEstimatingTokenizer(Tokenizer):
    def __init__(self, model_name: str, dir_path: Path) -> None:
        self.model_name = model_name
        self._tokenizer = AutoTokenizer.from_pretrained(model_name)

    async def tokenize(self, prompt: str) -> list[int]:
        return list(map(int, cast(list[str], self._tokenizer.tokenize(prompt))))

    async def estimate_token_count(self, prompt: str) -> int:
        tokens = self._tokenizer.tokenize(prompt)
        return len(tokens)


class JinaAIEmbedder(HuggingFaceEmbedder):
    def __init__(self, dir_path: Path) -> None:
        super().__init__(model_name="jinaai/jina-embeddings-v2-base-en", dir_path=dir_path)

        self._estimating_tokenizer = AutoTokenizerEstimatingTokenizer(self.model_name, dir_path)

    @property
    def id(self) -> str:
        return f"hugging-face/{self.model_name}"

    @property
    def max_tokens(self) -> int:
        return 128000

    def get_tokenizer(self) -> AutoTokenizerEstimatingTokenizer:
        return self._estimating_tokenizer
