from typing import Any, NewType, Union
import nanoid  # type: ignore

JSONSerializable = Union[str, int, float, bool, None, dict[str, Any], list[Any]]

UniqueId = NewType("UniqueId", str)


def generate_id() -> UniqueId:
    return UniqueId(nanoid.generate(size=10))
