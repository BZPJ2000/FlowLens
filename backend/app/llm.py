from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class LlmConfigError(RuntimeError):
    pass


class LlmCallError(RuntimeError):
    pass


@dataclass(frozen=True)
class TextAiSettings:
    base_url: str
    api_key: str
    model: str


def load_env_files() -> None:
    for path in _env_file_candidates():
        if not path.exists() or not path.is_file():
            continue
        _load_dotenv(path)


def load_text_ai_settings() -> TextAiSettings | None:
    load_env_files()
    if not _llm_enabled():
        return None

    api_key = os.getenv("TEXT_AI_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or ""
    if not api_key:
        return None

    base_url = (
        os.getenv("TEXT_AI_BASE_URL")
        or os.getenv("DEEPSEEK_BASE_URL")
        or "https://api.deepseek.com"
    )
    model = os.getenv("TEXT_AI_MODEL") or os.getenv("DEEPSEEK_MODEL") or "deepseek-chat"
    return TextAiSettings(base_url=base_url.rstrip("/"), api_key=api_key, model=model)


def chat_text(
    messages: list[dict[str, str]],
    *,
    settings: TextAiSettings | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1800,
    timeout: float = 90.0,
) -> str:
    settings = settings or load_text_ai_settings()
    if settings is None:
        raise LlmConfigError("TEXT_AI_API_KEY is not configured or LLM is disabled")

    payload = {
        "model": settings.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        f"{settings.base_url}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise LlmCallError(f"Text AI HTTP {exc.code}: {detail}") from exc
    except OSError as exc:
        raise LlmCallError(f"Text AI request failed: {exc}") from exc

    try:
        data: dict[str, Any] = json.loads(body)
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise LlmCallError(f"Text AI returned an unexpected response: {body[:500]}") from exc

    if not isinstance(content, str) or not content.strip():
        raise LlmCallError("Text AI returned empty content")
    return content.strip()


def _env_file_candidates() -> tuple[Path, ...]:
    configured = os.getenv("POLTAISHOW_ENV_FILE")
    paths = []
    if configured:
        paths.append(Path(configured).expanduser())
    paths.append(PROJECT_ROOT / ".env")
    # Local convenience: reuse the sibling Papyrus config when this repo sits next to it.
    paths.append(PROJECT_ROOT.parent / "Papyrus" / ".env")
    return tuple(paths)


def _load_dotenv(path: Path) -> None:
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _llm_enabled() -> bool:
    raw = os.getenv("POLTAISHOW_LLM_ENABLED")
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return (PROJECT_ROOT / ".env").exists()
