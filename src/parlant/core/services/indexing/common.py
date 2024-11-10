import asyncio
from typing import Awaitable, Callable


class ProgressReport:
    def __init__(self, progress_callback: Callable[[float], Awaitable[None]]) -> None:
        self._total = 0
        self._current = 0
        self._lock = asyncio.Lock()
        self._progress_callback = progress_callback

    @property
    def percentage(self) -> float:
        if self._total == 0:
            return 0.0
        return self._current / self._total * 100

    async def stretch(self, amount: int) -> None:
        async with self._lock:
            self._total += amount
            await self._progress_callback(self.percentage)

    async def increment(self, amount: int = 1) -> None:
        async with self._lock:
            self._current += amount
            await self._progress_callback(self.percentage)
