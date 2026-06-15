from __future__ import annotations

import pytest

from backend.app.state import app_state


@pytest.fixture(autouse=True)
def isolated_app_state(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("POLTAISHOW_LLM_ENABLED", "false")
    monkeypatch.delenv("TEXT_AI_API_KEY", raising=False)
    monkeypatch.delenv("TEXT_AI_BASE_URL", raising=False)
    monkeypatch.delenv("TEXT_AI_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)

    with app_state._lock:
        app_state.projects.clear()
        app_state.analyses.clear()
    yield
    with app_state._lock:
        app_state.projects.clear()
        app_state.analyses.clear()
