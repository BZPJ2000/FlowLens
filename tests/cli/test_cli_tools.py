from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from resources.scripts import function_analyzer, script_graph


def test_function_analyzer_writes_json_and_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "app.py").write_text("def main() -> int:\n    return 1\n", encoding="utf-8")
    json_path = tmp_path / "graph.json"

    function_analyzer.analyze_target(str(tmp_path), json_path=str(json_path), symbol_limit=10)

    output = capsys.readouterr().out
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert "Graph:" in output
    assert payload["symbols"][0]["qualified_name"] == "app.main"


def test_script_graph_writes_dot_when_graphviz_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "app.py").write_text(
        "def helper() -> int:\n"
        "    return 1\n\n"
        "def main() -> int:\n"
        "    return helper()\n",
        encoding="utf-8",
    )

    def fake_run(*args, **kwargs):
        raise FileNotFoundError("dot")

    monkeypatch.setattr(subprocess, "run", fake_run)
    output_base = tmp_path / "project_flow"

    script_graph.build_call_graph(str(tmp_path), str(output_base))

    dot_text = output_base.with_suffix(".dot").read_text(encoding="utf-8")
    output = capsys.readouterr().out
    assert "digraph static_flow" in dot_text
    assert "app.main" in dot_text
    assert "PNG render skipped" in output
