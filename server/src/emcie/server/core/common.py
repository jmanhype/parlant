from typing import NewType, Optional
import hashlib
import nanoid  # type: ignore


from emcie.common.base_models import DefaultBaseModel as DefaultBaseModel
from emcie.common.types.common import JSONSerializable as JSONSerializable

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
