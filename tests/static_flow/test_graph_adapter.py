from __future__ import annotations

from pathlib import Path

from backend.app.graph_adapter import to_frontend_payload
from modules.static_flow import analyze_project


def test_frontend_payload_contains_symbol_edges_and_project_file_tree(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Sample\n", encoding="utf-8")
    (tmp_path / "app.py").write_text(
        "def helper(value: int) -> int:\n"
        "    return value\n\n"
        "def main() -> int:\n"
        "    result = helper(1)\n"
        "    return result\n",
        encoding="utf-8",
    )

    graph = analyze_project(tmp_path)
    payload, file_details, report = to_frontend_payload(graph)

    assert payload["nodes"]
    assert payload["edges"]
    assert payload["project_files"]
    assert any(item["file_name"] == "README.md" and not item["has_symbols"] for item in payload["project_files"])
    assert any(edge["edge_type"] == "arg" and edge["source_slot"] == "1" for edge in payload["edges"])
    assert any(edge["edge_type"] == "return" and edge["target_slot"] == "result" for edge in payload["edges"])
    assert file_details
    assert "Project Analysis Report" in report
