from typing import Mapping, Optional, Sequence, TypeAlias, Union, Any


JSONSerializable: TypeAlias = Union[
    str,
    int,
    float,
    bool,
    None,
    Mapping[str, "JSONSerializable"],
    Sequence["JSONSerializable"],
    Optional[str],
    Optional[int],
    Optional[float],
    Optional[bool],
    Optional[None],
    Optional[Mapping[str, "JSONSerializable"]],
    Optional[Sequence["JSONSerializable"]],
]


def is_json_serializable(value: Any) -> bool:
    if isinstance(value, (str, int, float, bool, type(None))):
        return True
    elif isinstance(value, Mapping):
        return all(isinstance(k, str) and is_json_serializable(v) for k, v in value.items())
    elif isinstance(value, Sequence):
        return all(is_json_serializable(item) for item in value)
    else:
        return False
