from abc import ABC, abstractmethod
from typing import cast
from transformers import AutoTokenizer  # type: ignore


class Tokenizer(ABC):
    @abstractmethod
    async def tokenize(self, prompt: str) -> list[int]: ...

    @abstractmethod
    async def estimate_token_count(self, prompt: str) -> int: ...


class EstimatingTokenizer(Tokenizer): ...


class AutoTokenizerEstimatingTokenizer(EstimatingTokenizer):
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._tokenizer = AutoTokenizer.from_pretrained(model_name)

    async def tokenize(self, prompt: str) -> list[int]:
        return list(map(int, cast(list[str], self._tokenizer.tokenize(prompt))))

    async def estimate_token_count(self, prompt: str) -> int:
        tokens = self._tokenizer.tokenize(prompt)
        return len(tokens)
