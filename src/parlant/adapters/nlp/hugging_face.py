from collections.abc import Mapping
import os
from typing import Any, cast
import torch
from transformers import AutoModel, AutoTokenizer  # type: ignore
from parlant.core.nlp.tokenizer import Tokenizer
from parlant.core.nlp.embedding import Embedder, EmbeddingResult


class HuggingFaceEmbedder(Embedder):
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = AutoModel.from_pretrained(model_name, attn_implementation="eager")
        self._model.save_pretrained(os.environ.get("PARLANT_HOME", "/tmp"))
        self._model.eval()

        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._tokenizer.save_pretrained(os.environ.get("PARLANT_HOME", "/tmp"))

    async def embed(
        self,
        texts: list[str],
        hints: Mapping[str, Any] = {},
    ) -> EmbeddingResult:
        tokenized_texts = self._tokenizer.batch_encode_plus(
            texts, padding=True, truncation=True, return_tensors="pt"
        )

        with torch.no_grad():
            embeddings = self._model(**tokenized_texts).last_hidden_state[:, 0, :]

        return EmbeddingResult(vectors=embeddings.tolist())


class AutoTokenizerEstimatingTokenizer(Tokenizer):
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._tokenizer = AutoTokenizer.from_pretrained(model_name)

    async def tokenize(self, prompt: str) -> list[int]:
        return list(map(int, cast(list[str], self._tokenizer.tokenize(prompt))))

    async def estimate_token_count(self, prompt: str) -> int:
        tokens = self._tokenizer.tokenize(prompt)
        return len(tokens)


class JinaAIEmbedder(HuggingFaceEmbedder):
    def __init__(self) -> None:
        super().__init__(model_name="jinaai/jina-embeddings-v2-base-en")

        self._estimating_tokenizer = AutoTokenizerEstimatingTokenizer(self.model_name)

    @property
    def id(self) -> str:
        return f"hugging-face/{self.model_name}"

    @property
    def max_tokens(self) -> int:
        return 8192

    def get_tokenizer(self) -> AutoTokenizerEstimatingTokenizer:
        return self._estimating_tokenizer
