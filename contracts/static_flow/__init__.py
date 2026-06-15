"""Language-neutral static flow contracts.

Language adapters should map parser-specific output into these contracts.
The analysis and visualization layers should depend on this package, not on
Python AST, Tree-sitter CST, or any other language-specific representation.
"""

from .edge import StaticFlowEdge, StaticFlowEdgeKind, StaticResolution
from .graph import StaticProjectGraph
from .scan import StaticScanStats
from .signature import StaticLocalVariable, StaticParam, StaticSignature
from .symbol import LanguageId, MethodKind, StaticSymbol, StaticSymbolKind

__all__ = [
    "LanguageId",
    "MethodKind",
    "StaticFlowEdge",
    "StaticFlowEdgeKind",
    "StaticLocalVariable",
    "StaticParam",
    "StaticProjectGraph",
    "StaticScanStats",
    "StaticResolution",
    "StaticSignature",
    "StaticSymbol",
    "StaticSymbolKind",
]
