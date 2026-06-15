from __future__ import annotations

from dataclasses import dataclass

from ._serde import SerializableDataclass


@dataclass(frozen=True, kw_only=True)
class StaticScanStats(SerializableDataclass):
    target_path: str
    files_discovered: int = 0
    files_parsed: int = 0
    files_failed: int = 0
    files_skipped: int = 0
    elapsed_ms: int = 0
