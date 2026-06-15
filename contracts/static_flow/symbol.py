from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ._serde import SerializableDataclass


class LanguageId(str, Enum):
    PYTHON = "python"
    JAVA = "java"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    UNKNOWN = "unknown"


class StaticSymbolKind(str, Enum):
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"


class MethodKind(str, Enum):
    INSTANCE = "instance_method"
    CLASS = "class_method"
    STATIC = "static_method"
    UNKNOWN = "unknown"


@dataclass(frozen=True, kw_only=True)
class StaticSymbol(SerializableDataclass):
    symbol_id: str
    language: LanguageId
    kind: StaticSymbolKind
    qualified_name: str
    display_name: str
    file_path: str
    start_line: int
    end_line: int
    parent_symbol_id: str | None = None
    method_kind: MethodKind | None = None
