from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

from modules.static_flow import AnalyzeProjectOptions, analyze_project

from .graph_adapter import to_frontend_payload
from .models import AnalysisRecord
from .state import app_state


def run_analysis(record: AnalysisRecord) -> None:
    try:
        app_state.update_progress(
            record.analysis_id,
            status="parsing",
            progress_pct=15,
            message="Scanning project files",
            detail=str(record.source_path),
        )
        graph = analyze_project(
            record.source_path,
            options=AnalyzeProjectOptions(workers=8, max_file_size_kb=1024),
        )
        app_state.update_progress(
            record.analysis_id,
            status="building",
            progress_pct=75,
            message="Building visualization graph",
            detail=f"{len(graph.symbols)} symbols, {len(graph.edges)} edges",
        )
        frontend_graph, file_details, report_md = to_frontend_payload(graph)
        record.graph = graph
        record.frontend_graph = frontend_graph
        record.file_details = file_details
        record.report_md = report_md
        app_state.update_progress(
            record.analysis_id,
            status="completed",
            progress_pct=100,
            message="Analysis completed",
            detail=f"{len(frontend_graph['nodes'])} files, {len(frontend_graph['edges'])} edges",
        )
    except Exception as exc:  # pragma: no cover - surfaced through API in integration use
        record.error_message = str(exc)
        app_state.update_progress(
            record.analysis_id,
            status="failed",
            progress_pct=100,
            message=str(exc),
        )


def resolve_source_path(source_url: str) -> Path:
    value = source_url.strip()
    if value.startswith("file://"):
        parsed = urlparse(value)
        value = unquote(parsed.path)
        if parsed.netloc:
            value = f"//{parsed.netloc}{value}"
        elif len(value) >= 3 and value[0] == "/" and value[2] == ":":
            value = value[1:]
    path = Path(value).expanduser().resolve()
    if not path.exists():
        raise ValueError(
            "Only existing local paths or file:// paths are supported by the lightweight backend."
        )
    return path
