from typing import NewType
import nanoid  # type: ignore

UniqueId = NewType("UniqueId", str)


def generate_id() -> UniqueId:
    return UniqueId(nanoid.generate(size=10))
