from dataclasses import dataclass
from typing import TypeVar, Generic, Sequence


@dataclass
class Shot:
    description: str
    """An explanation of what makes this shot interesting"""


TShot = TypeVar("TShot", bound=Shot)


class ShotCollection(Generic[TShot]):
    def __init__(self, initial_shots: Sequence[TShot]) -> None:
        self._shots: list[TShot] = list(initial_shots)

    async def append(
        self,
        shot: TShot,
    ) -> None:
        self._shots.append(shot)

    async def insert(
        self,
        shot: TShot,
        index: int = 0,
    ) -> None:
        self._shots.insert(index, shot)

    async def list(self) -> Sequence[TShot]:
        return self._shots

    async def remove(
        self,
        shot: TShot,
    ) -> None:
        self._shots.remove(shot)

    async def clear(self) -> None:
        self._shots.clear()
