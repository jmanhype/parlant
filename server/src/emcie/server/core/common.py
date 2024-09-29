import asyncio
from typing import NewType, Optional, TypeAlias
import hashlib
import nanoid  # type: ignore


from emcie.common.base_models import DefaultBaseModel as _DefaultBaseModel
from emcie.common.types.common import JSONSerializable as _JSONSerializable


DefaultBaseModel: TypeAlias = _DefaultBaseModel
JSONSerializable: TypeAlias = _JSONSerializable

UniqueId = NewType("UniqueId", str)


class ItemNotFoundError(Exception):
    def __init__(self, item_id: UniqueId, message: Optional[str] = None) -> None:
        super().__init__(f"Item '{item_id}' not found" + (f": {message}" if message else ""))


def generate_id() -> UniqueId:
    return UniqueId(nanoid.generate(size=10))


def md5_checksum(input: str) -> str:
    md5_hash = hashlib.md5()
    md5_hash.update(input.encode("utf-8"))

    return md5_hash.hexdigest()


class ProgressReport:
    def __init__(self) -> None:
        self._total = 0
        self._current = 0
        self._lock = asyncio.Lock()

    @property
    def percentage(self) -> float:
        if self._total == 0:
            return 0.0
        return self._current / self._total * 100

    async def stretch(self, amount: int) -> None:
        async with self._lock:
            self._total += amount

    async def increment(self, amount: int = 1) -> None:
        async with self._lock:
            self._current += amount
