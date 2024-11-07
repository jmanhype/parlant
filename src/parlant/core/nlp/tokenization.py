from abc import ABC, abstractmethod


class EstimatingTokenizer(ABC):
    @abstractmethod
    async def estimate_token_count(self, prompt: str) -> int: ...
