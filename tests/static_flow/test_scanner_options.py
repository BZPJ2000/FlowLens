from __future__ import annotations

from pathlib import Path

from modules.static_flow import AnalyzeProjectOptions, analyze_project


def test_scanner_reports_missing_target_as_warning(tmp_path: Path) -> None:
    graph = analyze_project(tmp_path / "missing")

    assert graph.symbols == ()
    assert graph.scan_stats is not None
    assert graph.scan_stats.files_discovered == 0
    assert "Project target does not exist" in graph.warnings[0]


def test_scanner_excludes_hidden_archive_and_custom_dirs(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def main() -> int:\n    return 1\n", encoding="utf-8")
    (tmp_path / "_archive").mkdir()
    (tmp_path / "_archive" / "old.py").write_text("def old():\n    pass\n", encoding="utf-8")
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "lib.py").write_text("def lib():\n    pass\n", encoding="utf-8")
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "hidden.py").write_text("def hidden():\n    pass\n", encoding="utf-8")

    options = AnalyzeProjectOptions(
        excluded_dir_names=AnalyzeProjectOptions().excluded_dir_names | {"vendor"},
        workers=1,
    )
    graph = analyze_project(tmp_path, options=options)

    assert graph.scan_stats is not None
    assert graph.scan_stats.files_discovered == 1
    assert graph.scan_stats.files_skipped == 3
    assert {symbol.symbol_id for symbol in graph.symbols} == {"app.main"}
