from __future__ import annotations

from pathlib import Path
from threading import RLock
from uuid import uuid4

from .models import AnalysisRecord, ProjectRecord


class AppState:
    def __init__(self) -> None:
        self._lock = RLock()
        self.projects: dict[str, ProjectRecord] = {}
        self.analyses: dict[str, AnalysisRecord] = {}

    def create_analysis(
        self,
        *,
        source_path: Path,
        source_type: str,
        source_url: str,
        project_name: str | None = None,
    ) -> AnalysisRecord:
        project_id = uuid4().hex
        analysis_id = uuid4().hex
        name = project_name or source_path.name or "project"
        project = ProjectRecord(
            project_id=project_id,
            name=name,
            source_type=source_type,
            source_url=source_url,
            analysis_ids=[analysis_id],
        )
        analysis = AnalysisRecord(
            analysis_id=analysis_id,
            project_id=project_id,
            project_name=name,
            source_type=source_type,
            source_url=source_url,
            source_path=source_path,
        )
        with self._lock:
            self.projects[project_id] = project
            self.analyses[analysis_id] = analysis
        return analysis

    def list_projects(self) -> list[ProjectRecord]:
        with self._lock:
            return sorted(self.projects.values(), key=lambda item: item.created_at, reverse=True)

    def get_project(self, project_id: str) -> ProjectRecord | None:
        with self._lock:
            return self.projects.get(project_id)

    def get_analysis(self, analysis_id: str) -> AnalysisRecord | None:
        with self._lock:
            return self.analyses.get(analysis_id)

    def delete_project(self, project_id: str) -> bool:
        with self._lock:
            project = self.projects.pop(project_id, None)
            if project is None:
                return False
            for analysis_id in project.analysis_ids:
                self.analyses.pop(analysis_id, None)
            return True

    def update_progress(
        self,
        analysis_id: str,
        *,
        status: str,
        progress_pct: int,
        message: str,
        detail: str = "",
    ) -> None:
        with self._lock:
            analysis = self.analyses[analysis_id]
            analysis.status = status  # type: ignore[assignment]
            analysis.progress_pct = progress_pct
            analysis.message = message
            analysis.detail = detail


app_state = AppState()
