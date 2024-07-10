from typing import Any, Mapping, NewType, Sequence, Type, TypeVar, Union
import nanoid  # type: ignore


JSONSerializable = Union[
    str,
    int,
    float,
    bool,
    None,
    Mapping[str, "JSONSerializable"],
    Sequence["JSONSerializable"],
]


UniqueId = NewType("UniqueId", str)
T = TypeVar("T")


def generate_id() -> UniqueId:
    return UniqueId(nanoid.generate(size=10))


def create_instance_from_dict(
    data_class: Type[T],
    attributes_dict: dict[str, Any],
) -> T:
    return data_class(**{k: attributes_dict[k] for k in data_class.__annotations__.keys()})
