from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

import backend.app.main as main_module
from backend.app.main import app


def test_local_project_import_builds_frontend_graph() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/projects/import",
        json={"source_type": "local", "source_url": "."},
    )
    assert response.status_code == 200
    analysis_id = response.json()["analysis_id"]

    status_response = client.get(f"/api/v1/analyses/{analysis_id}")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "completed"

    graph_response = client.get(f"/api/v1/analyses/{analysis_id}/graph")
    assert graph_response.status_code == 200
    payload = graph_response.json()
    assert payload["nodes"]
    assert payload["edges"]
    assert payload["project_files"]
    assert any(node["language"] in {"python", "typescript", "javascript"} for node in payload["nodes"])
    assert all("source_slot" in edge and "target_slot" in edge for edge in payload["edges"])
    assert {edge["edge_type"] for edge in payload["edges"]} & {"call", "arg", "return"}

    first_function = next(
        node["functions"][0]
        for node in payload["nodes"]
        if node["functions"]
    )
    assert first_function["qualified_name"]
    assert first_function["start_line"] >= 1
    assert first_function["end_line"] >= first_function["start_line"]

    file_id = payload["nodes"][0]["id"]
    detail_response = client.get(f"/api/v1/analyses/{analysis_id}/files/{file_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["file_path"]

    source_response = client.get(
        f"/api/v1/analyses/{analysis_id}/source",
        params={
            "file_path": payload["nodes"][0]["file_path"],
            "start_line": first_function["start_line"],
            "end_line": first_function["end_line"],
        },
    )
    assert source_response.status_code == 200
    source_payload = source_response.json()
    assert source_payload["content"]
    assert source_payload["start_line"] == first_function["start_line"]

    outside_response = client.get(
        f"/api/v1/analyses/{analysis_id}/source",
        params={"file_path": "C:/Windows/win.ini"},
    )
    assert outside_response.status_code in {403, 404}

    selected_id = first_function["id"]
    chat_response = client.post(
        f"/api/v1/analyses/{analysis_id}/chat",
        json={
            "message": "解释我选中的符号关系",
            "selected_symbol_ids": [selected_id],
        },
    )
    assert chat_response.status_code == 200
    assert first_function["qualified_name"] in chat_response.json()["reply"]


def test_chat_uses_llm_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/projects/import",
        json={"source_type": "local", "source_url": "."},
    )
    assert response.status_code == 200
    analysis_id = response.json()["analysis_id"]

    captured = {}

    def fake_chat_text(messages, **kwargs):
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return "LLM answer from DeepSeek"

    monkeypatch.setattr(main_module, "chat_text", fake_chat_text)
    monkeypatch.setenv("POLTAISHOW_LLM_ENABLED", "true")
    monkeypatch.setenv("TEXT_AI_API_KEY", "test-key")
    monkeypatch.setenv("TEXT_AI_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("TEXT_AI_MODEL", "deepseek-chat")

    chat_response = client.post(
        f"/api/v1/analyses/{analysis_id}/chat",
        json={"message": "总结这个项目"},
    )

    assert chat_response.status_code == 200
    assert chat_response.json()["reply"] == "LLM answer from DeepSeek"
    assert "项目静态分析上下文" in captured["messages"][1]["content"]
