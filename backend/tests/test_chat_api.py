from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

import backend.app.main as main_module
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


def test_chat_falls_back_to_static_graph_when_llm_disabled(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "def helper(value: int) -> int:\n"
        "    return value\n\n"
        "def main() -> int:\n"
        "    result = helper(1)\n"
        "    return result\n",
        encoding="utf-8",
    )
    client = TestClient(app)
    analysis_id, _ = _import_project(client, tmp_path)

    response = client.post(
        f"/api/v1/analyses/{analysis_id}/chat",
        json={"message": "what flow edges exist?", "selected_symbol_ids": []},
    )

    assert response.status_code == 200
    assert "静态关系边" in response.json()["reply"]


def test_chat_selected_symbols_include_neighbor_edges(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "def helper(value: int) -> int:\n"
        "    return value\n\n"
        "def main() -> int:\n"
        "    result = helper(1)\n"
        "    return result\n",
        encoding="utf-8",
    )
    client = TestClient(app)
    analysis_id, graph = _import_project(client, tmp_path)
    selected_id = next(
        fn["id"]
        for node in graph["nodes"]
        for fn in node["functions"]
        if fn["id"].endswith("app.main")
    )

    response = client.post(
        f"/api/v1/analyses/{analysis_id}/chat",
        json={"message": "explain selected", "selected_symbol_ids": [selected_id]},
    )

    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "当前选中了 1 个符号" in reply
    assert "app.helper" in reply
    assert "1 -> value" in reply


def test_chat_stream_sends_chunks_and_done(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def main() -> int:\n    return 1\n", encoding="utf-8")
    client = TestClient(app)
    analysis_id, _ = _import_project(client, tmp_path)

    with client.stream(
        "POST",
        f"/api/v1/analyses/{analysis_id}/chat/stream",
        json={"message": "files", "selected_symbol_ids": []},
    ) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert '"type": "chunk"' in body
    assert '"type": "done"' in body


def test_chat_uses_llm_context_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "app.py").write_text("def main() -> int:\n    return 1\n", encoding="utf-8")
    client = TestClient(app)
    analysis_id, _ = _import_project(client, tmp_path)
    captured: dict[str, object] = {}

    def fake_chat_text(messages, **kwargs):
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return "DeepSeek answer"

    monkeypatch.setattr(main_module, "chat_text", fake_chat_text)
    monkeypatch.setenv("POLTAISHOW_LLM_ENABLED", "true")
    monkeypatch.setenv("TEXT_AI_API_KEY", "test-key")

    response = client.post(
        f"/api/v1/analyses/{analysis_id}/chat",
        json={"message": "summarize project", "selected_symbol_ids": []},
    )

    assert response.status_code == 200
    assert response.json()["reply"] == "DeepSeek answer"
    messages = captured["messages"]
    assert isinstance(messages, list)
    assert "项目静态分析上下文" in messages[1]["content"]
