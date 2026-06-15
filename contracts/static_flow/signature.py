from __future__ import annotations

from dataclasses import dataclass

from ._serde import SerializableDataclass


@dataclass(frozen=True, kw_only=True)
class StaticParam(SerializableDataclass):
    name: str
    type_annotation: str | None = None
    default_value: str | None = None


@dataclass(frozen=True, kw_only=True)
class StaticSignature(SerializableDataclass):
    symbol_id: str
    parameters: tuple[StaticParam, ...] = ()
    return_type: str | None = None


@dataclass(frozen=True, kw_only=True)
class StaticLocalVariable(SerializableDataclass):
    symbol_id: str
    name: str
    line_number: int
    value_preview: str | None = None
    type_annotation: str | None = None
