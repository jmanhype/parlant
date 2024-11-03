from abc import ABC, abstractmethod


class Tokenizer(ABC):
    @abstractmethod
    async def tokenize(self, prompt: str) -> list[int]: ...

    @abstractmethod
    async def estimate_token_count(self, prompt: str) -> int: ...


class EstimatingTokenizer(Tokenizer): ...
