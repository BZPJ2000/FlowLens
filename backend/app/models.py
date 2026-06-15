from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from contracts.static_flow import StaticProjectGraph


AnalysisStatus = Literal["pending", "parsing", "analyzing", "building", "completed", "failed"]


@dataclass
class AnalysisRecord:
    analysis_id: str
    project_id: str
    project_name: str
    source_type: str
    source_url: str
    source_path: Path
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: AnalysisStatus = "pending"
    progress_pct: int = 0
    message: str = "Queued"
    detail: str = ""
    error_message: str = ""
    graph: StaticProjectGraph | None = None
    frontend_graph: dict | None = None
    file_details: dict[str, dict] = field(default_factory=dict)
    report_md: str = ""

    @property
    def file_count(self) -> int:
        if self.graph and self.graph.scan_stats:
            return self.graph.scan_stats.files_parsed
        return 0

    def progress_event(self) -> dict:
        return {
            "analysis_id": self.analysis_id,
            "status": self.status,
            "progress_pct": self.progress_pct,
            "message": self.message,
            "detail": self.detail,
        }


@dataclass
class ProjectRecord:
    project_id: str
    name: str
    source_type: str
    source_url: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    analysis_ids: list[str] = field(default_factory=list)
