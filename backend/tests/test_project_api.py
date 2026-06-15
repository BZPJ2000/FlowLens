from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app


def _import_project(client: TestClient, project: Path) -> tuple[str, str]:
    response = client.post(
        "/api/v1/projects/import",
        json={"source_type": "local", "source_url": str(project)},
    )
    assert response.status_code == 200
    payload = response.json()
    return payload["project_id"], payload["analysis_id"]


def test_list_projects_reports_latest_analysis(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def main() -> int:\n    return 1\n", encoding="utf-8")
    client = TestClient(app)
    project_id, analysis_id = _import_project(client, tmp_path)

    response = client.get("/api/v1/projects")

    assert response.status_code == 200
    projects = response.json()
    assert len(projects) == 1
    assert projects[0]["project_id"] == project_id
    assert projects[0]["latest_analysis"]["analysis_id"] == analysis_id
    assert projects[0]["latest_analysis"]["status"] == "completed"


def test_delete_project_removes_project_and_analysis(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def main() -> int:\n    return 1\n", encoding="utf-8")
    client = TestClient(app)
    project_id, analysis_id = _import_project(client, tmp_path)

    response = client.delete(f"/api/v1/projects/{project_id}")

    assert response.status_code == 200
    assert client.get("/api/v1/projects").json() == []
    assert client.get(f"/api/v1/analyses/{analysis_id}").status_code == 404


def test_reanalyze_resets_and_rebuilds_graph(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def first() -> int:\n    return 1\n", encoding="utf-8")
    client = TestClient(app)
    _, analysis_id = _import_project(client, tmp_path)

    (tmp_path / "app.py").write_text(
        "def first() -> int:\n"
        "    return second()\n\n"
        "def second() -> int:\n"
        "    return 2\n",
        encoding="utf-8",
    )
    response = client.post(f"/api/v1/analyses/{analysis_id}/reanalyze")

    assert response.status_code == 200
    graph = client.get(f"/api/v1/analyses/{analysis_id}/graph").json()
    function_ids = {
        fn["id"]
        for node in graph["nodes"]
        for fn in node["functions"]
    }
    assert any(symbol_id.endswith("app.second") for symbol_id in function_ids)
