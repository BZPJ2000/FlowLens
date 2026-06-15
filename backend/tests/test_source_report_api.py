from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app


def _import_project(client: TestClient, project: Path) -> tuple[str, dict]:
    response = client.post(
        "/api/v1/projects/import",
        json={"source_type": "local", "source_url": str(project)},
    )
    assert response.status_code == 200
    analysis_id = response.json()["analysis_id"]
    graph = client.get(f"/api/v1/analyses/{analysis_id}/graph").json()
    return analysis_id, graph


def test_source_endpoint_returns_requested_code_window(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text(
        "def helper() -> int:\n"
        "    return 1\n\n"
        "def main() -> int:\n"
        "    value = helper()\n"
        "    return value\n",
        encoding="utf-8",
    )
    client = TestClient(app)
    analysis_id, graph = _import_project(client, tmp_path)
    main_fn = next(
        fn
        for node in graph["nodes"]
        for fn in node["functions"]
        if fn["id"].endswith("app.main")
    )

    response = client.get(
        f"/api/v1/analyses/{analysis_id}/source",
        params={
            "file_path": str(source),
            "start_line": main_fn["start_line"],
            "end_line": main_fn["end_line"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["language"] == "python"
    assert payload["start_line"] == main_fn["start_line"]
    assert "def main" in payload["content"]


def test_source_endpoint_blocks_paths_outside_project(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def main() -> int:\n    return 1\n", encoding="utf-8")
    outside = tmp_path.parent / "outside.py"
    outside.write_text("def outside():\n    pass\n", encoding="utf-8")
    client = TestClient(app)
    analysis_id, _ = _import_project(client, tmp_path)

    response = client.get(
        f"/api/v1/analyses/{analysis_id}/source",
        params={"file_path": str(outside)},
    )

    assert response.status_code == 403


def test_report_endpoint_contains_scan_summary(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def main() -> int:\n    return 1\n", encoding="utf-8")
    client = TestClient(app)
    analysis_id, _ = _import_project(client, tmp_path)

    response = client.get(f"/api/v1/analyses/{analysis_id}/report")

    assert response.status_code == 200
    payload = response.json()
    assert payload["architecture_summary"] == "Static project graph summary"
    assert "Project Analysis Report" in payload["content_md"]
    assert "Symbols:" in payload["content_md"]
