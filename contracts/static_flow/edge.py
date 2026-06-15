from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ._serde import SerializableDataclass


class StaticFlowEdgeKind(str, Enum):
    CONTAINS = "contains"
    CALL = "call"
    ARG = "arg"
    RETURN = "return"
    UNRESOLVED_CALL = "unresolved_call"


class StaticResolution(str, Enum):
    RESOLVED = "resolved"
    PARTIAL = "partial"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, kw_only=True)
class StaticFlowEdge(SerializableDataclass):
    edge_id: str
    kind: StaticFlowEdgeKind
    source_symbol_id: str
    target_symbol_id: str | None
    source_slot: str | None = None
    target_slot: str | None = None
    detail: str | None = None
    line_number: int | None = None
    resolution: StaticResolution = StaticResolution.RESOLVED
