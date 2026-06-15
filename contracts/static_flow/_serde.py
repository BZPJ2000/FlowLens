from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
from types import UnionType
from typing import Any, TypeVar, Union, get_args, get_origin, get_type_hints

T = TypeVar("T")


def _serialize_value(value: Any) -> Any:
    if is_dataclass(value):
        return {field.name: _serialize_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    return value


def _deserialize_value(expected_type: Any, value: Any) -> Any:
    if value is None:
        return None

    origin = get_origin(expected_type)
    args = get_args(expected_type)

    if origin in (list, tuple):
        if len(args) == 2 and args[1] is Ellipsis:
            item_type = args[0]
            items = [_deserialize_value(item_type, item) for item in value]
        elif args:
            items = [
                _deserialize_value(item_type, item)
                for item_type, item in zip(args, value, strict=False)
            ]
        else:
            items = list(value)
        return tuple(items) if origin is tuple else items

    if origin is dict:
        key_type, item_type = args if len(args) == 2 else (Any, Any)
        return {
            _deserialize_value(key_type, key): _deserialize_value(item_type, item)
            for key, item in value.items()
        }

    if origin in (Union, UnionType):
        non_none_args = [arg for arg in args if arg is not type(None)]
        if len(non_none_args) == 1:
            return _deserialize_value(non_none_args[0], value)

    if isinstance(expected_type, type):
        if issubclass(expected_type, Enum):
            return expected_type(value)
        if is_dataclass(expected_type):
            hints = get_type_hints(expected_type)
            kwargs = {
                field.name: _deserialize_value(hints.get(field.name, Any), value[field.name])
                for field in fields(expected_type)
            }
            return expected_type(**kwargs)

    return value


class SerializableDataclass:
    def to_dict(self) -> dict[str, Any]:
        return _serialize_value(self)

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        return _deserialize_value(cls, data)
