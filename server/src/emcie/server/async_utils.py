from __future__ import annotations
import asyncio


class Timeout:
    @staticmethod
    def none() -> Timeout:
        return Timeout(0)

    def __init__(self, seconds: float) -> None:
        self._creation = self._now()
        self._expiration = self._creation + seconds

    def expired(self) -> bool:
        return self.remaining() == 0

    def remaining(self) -> float:
        return max(0, self._expiration - self._now())

    def _now(self) -> float:
        return asyncio.get_event_loop().time()
