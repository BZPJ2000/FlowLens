from __future__ import annotations

import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app


def _write_sample_project(root: Path) -> Path:
    project = root / "sample"
    project.mkdir()
    (project / "math_ops.py").write_text(
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n\n"
        "def main() -> int:\n"
        "    total = add(1, 2)\n"
        "    return total\n",
        encoding="utf-8",
    )
    return project


def test_import_rejects_missing_local_path(tmp_path: Path) -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/projects/import",
        json={"source_type": "local", "source_url": str(tmp_path / "missing")},
    )

    assert response.status_code == 400
    assert "Only existing local paths" in response.json()["detail"]


def test_import_accepts_file_url_path(tmp_path: Path) -> None:
    project = _write_sample_project(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/api/v1/projects/import",
        json={"source_type": "local", "source_url": project.as_uri()},
    )

    assert response.status_code == 200
    analysis_id = response.json()["analysis_id"]
    status = client.get(f"/api/v1/analyses/{analysis_id}").json()
    assert status["status"] == "completed"
    assert status["file_count"] == 1


def test_archive_upload_extracts_and_analyzes_zip(tmp_path: Path) -> None:
    project = _write_sample_project(tmp_path)
    archive_path = tmp_path / "sample.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for path in project.rglob("*"):
            archive.write(path, path.relative_to(tmp_path))

    client = TestClient(app)
    response = client.post(
        "/api/v1/projects/import/upload",
        files={"file": ("sample.zip", archive_path.read_bytes(), "application/zip")},
    )

    assert response.status_code == 200
    analysis_id = response.json()["analysis_id"]
    graph = client.get(f"/api/v1/analyses/{analysis_id}/graph").json()
    function_ids = {
        fn["id"]
        for node in graph["nodes"]
        for fn in node["functions"]
    }
    assert any(symbol_id.endswith("math_ops.add") for symbol_id in function_ids)
    assert any(edge["edge_type"] == "arg" for edge in graph["edges"])


def test_archive_upload_rejects_unsupported_extension(tmp_path: Path) -> None:
    archive_path = tmp_path / "sample.txt"
    archive_path.write_text("not an archive", encoding="utf-8")
    client = TestClient(app)

    response = client.post(
        "/api/v1/projects/import/upload",
        files={"file": ("sample.txt", archive_path.read_bytes(), "text/plain")},
    )

    assert response.status_code == 400
    assert "Only .zip" in response.json()["detail"]
