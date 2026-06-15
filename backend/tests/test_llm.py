from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app import llm


def test_load_text_ai_settings_reads_configured_env_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "POLTAISHOW_LLM_ENABLED=true\n"
        "TEXT_AI_BASE_URL=https://api.deepseek.com/\n"
        "TEXT_AI_API_KEY=secret-value\n"
        "TEXT_AI_MODEL=deepseek-chat\n",
        encoding="utf-8",
    )
    for key in [
        "POLTAISHOW_LLM_ENABLED",
        "TEXT_AI_BASE_URL",
        "TEXT_AI_API_KEY",
        "TEXT_AI_MODEL",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_MODEL",
    ]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("POLTAISHOW_ENV_FILE", str(env_file))

    settings = llm.load_text_ai_settings()

    assert settings is not None
    assert settings.base_url == "https://api.deepseek.com"
    assert settings.api_key == "secret-value"
    assert settings.model == "deepseek-chat"


def test_chat_text_sends_openai_compatible_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {"choices": [{"message": {"content": "model reply"}}]},
                ensure_ascii=False,
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)

    reply = llm.chat_text(
        [{"role": "user", "content": "hello"}],
        settings=llm.TextAiSettings(
            base_url="https://api.deepseek.com",
            api_key="test-key",
            model="deepseek-chat",
        ),
        max_tokens=128,
    )

    assert reply == "model reply"
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["body"]["model"] == "deepseek-chat"
    assert captured["body"]["messages"][0]["content"] == "hello"
    assert captured["body"]["max_tokens"] == 128
    assert captured["headers"]["Authorization"] == "Bearer test-key"
