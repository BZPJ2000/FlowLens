from __future__ import annotations

from dataclasses import dataclass

from .edge import StaticFlowEdge
from ._serde import SerializableDataclass
from .scan import StaticScanStats
from .signature import StaticLocalVariable, StaticSignature
from .symbol import StaticSymbol


@dataclass(frozen=True, kw_only=True)
class StaticProjectGraph(SerializableDataclass):
    project_root: str
    symbols: tuple[StaticSymbol, ...]
    signatures: tuple[StaticSignature, ...]
    local_variables: tuple[StaticLocalVariable, ...]
    edges: tuple[StaticFlowEdge, ...]
    warnings: tuple[str, ...] = ()
    scan_stats: StaticScanStats | None = None
