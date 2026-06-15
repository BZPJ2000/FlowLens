from __future__ import annotations

from pathlib import Path

from contracts.static_flow import (
    LanguageId,
    MethodKind,
    StaticFlowEdgeKind,
    StaticSymbolKind,
)
from modules.static_flow import (
    AnalyzeProjectOptions,
    analyze_project,
    format_static_flow_report,
    format_static_flow_summary,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_example_file_builds_static_project_graph() -> None:
    graph = analyze_project(REPO_ROOT / "resources" / "fixtures" / "example.py")

    assert [symbol.symbol_id for symbol in graph.symbols] == [
        "example.compute",
        "example.add",
        "example.Calc",
        "example.Calc.multiply",
        "example.main",
    ]
    assert {symbol.language for symbol in graph.symbols} == {LanguageId.PYTHON}

    multiply = next(symbol for symbol in graph.symbols if symbol.symbol_id == "example.Calc.multiply")
    assert multiply.kind is StaticSymbolKind.METHOD
    assert multiply.method_kind is MethodKind.STATIC

    assert any(
        edge.kind is StaticFlowEdgeKind.CALL
        and edge.source_symbol_id == "example.compute"
        and edge.target_symbol_id == "example.add"
        for edge in graph.edges
    )
    assert any(
        edge.kind is StaticFlowEdgeKind.ARG
        and edge.source_symbol_id == "example.main"
        and edge.target_symbol_id == "example.compute"
        and edge.source_slot == "3"
        and edge.target_slot == "a"
        for edge in graph.edges
    )
    assert any(
        edge.kind is StaticFlowEdgeKind.RETURN
        and edge.source_symbol_id == "example.compute"
        and edge.target_symbol_id == "example.main"
        and edge.target_slot == "result"
        for edge in graph.edges
    )
    assert any(
        edge.kind is StaticFlowEdgeKind.CALL
        and edge.source_symbol_id == "example.main"
        and edge.target_symbol_id == "example.Calc.multiply"
        for edge in graph.edges
    )


def test_project_analyzer_resolves_simple_cross_file_imports(tmp_path: Path) -> None:
    (tmp_path / "math_ops.py").write_text(
        "def add(x: int, y: int) -> int:\n    return x + y\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "from math_ops import add\n\n"
        "def compute(a: int, b: int) -> int:\n"
        "    result = add(a, b)\n"
        "    return result\n",
        encoding="utf-8",
    )

    graph = analyze_project(tmp_path)

    assert {symbol.symbol_id for symbol in graph.symbols} == {
        "app.compute",
        "math_ops.add",
    }
    assert any(
        edge.kind is StaticFlowEdgeKind.CALL
        and edge.source_symbol_id == "app.compute"
        and edge.target_symbol_id == "math_ops.add"
        for edge in graph.edges
    )
    assert any(
        edge.kind is StaticFlowEdgeKind.RETURN
        and edge.source_symbol_id == "math_ops.add"
        and edge.target_symbol_id == "app.compute"
        and edge.target_slot == "result"
        for edge in graph.edges
    )


def test_same_line_repeated_calls_have_unique_edge_ids(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "def quote(value: str) -> str:\n"
        "    return value\n\n"
        "def render(a: str, b: str) -> str:\n"
        "    return quote(a) + quote(b)\n",
        encoding="utf-8",
    )

    graph = analyze_project(tmp_path)

    edge_ids = [edge.edge_id for edge in graph.edges]
    assert len(edge_ids) == len(set(edge_ids))
    assert sum(
        1
        for edge in graph.edges
        if edge.kind is StaticFlowEdgeKind.CALL
        and edge.source_symbol_id == "app.render"
        and edge.target_symbol_id == "app.quote"
    ) == 2


def test_typescript_tree_sitter_adapter_finds_symbols_and_value_edges(tmp_path: Path) -> None:
    (tmp_path / "math.ts").write_text(
        "export function sum(a: number, b: number): number {\n"
        "  return a + b;\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "App.tsx").write_text(
        "import { sum } from './math';\n\n"
        "const label = (value: number): string => format(value);\n\n"
        "export function App(): string {\n"
        "  const total = sum(1, 2);\n"
        "  const text = label(total);\n"
        "  return text;\n"
        "}\n",
        encoding="utf-8",
    )

    graph = analyze_project(tmp_path)

    assert {"math.sum", "App.label", "App.App"} <= {symbol.symbol_id for symbol in graph.symbols}
    assert any(symbol.language is LanguageId.TYPESCRIPT for symbol in graph.symbols)
    assert any(
        edge.kind is StaticFlowEdgeKind.ARG
        and edge.source_symbol_id == "App.App"
        and edge.target_symbol_id == "math.sum"
        and edge.source_slot == "1"
        and edge.target_slot == "a"
        for edge in graph.edges
    )
    assert any(
        edge.kind is StaticFlowEdgeKind.RETURN
        and edge.source_symbol_id == "math.sum"
        and edge.target_symbol_id == "App.App"
        and edge.target_slot == "total"
        for edge in graph.edges
    )
    assert any(
        edge.kind is StaticFlowEdgeKind.CALL
        and edge.source_symbol_id == "App.App"
        and edge.target_symbol_id == "App.label"
        for edge in graph.edges
    )


def test_project_directory_import_is_the_primary_path(tmp_path: Path) -> None:
    package = tmp_path / "shop"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "pricing.py").write_text(
        "def total(price: float, quantity: int) -> float:\n"
        "    return price * quantity\n",
        encoding="utf-8",
    )
    (package / "checkout.py").write_text(
        "from shop.pricing import total\n\n"
        "class Checkout:\n"
        "    @staticmethod\n"
        "    def run(price: float, quantity: int) -> float:\n"
        "        amount = total(price, quantity)\n"
        "        return amount\n",
        encoding="utf-8",
    )
    (tmp_path / "_archive").mkdir()
    (tmp_path / "_archive" / "ignored.py").write_text(
        "def ignored() -> None:\n    return None\n",
        encoding="utf-8",
    )
    (tmp_path / ".pytest_tmp_active").mkdir()
    (tmp_path / ".pytest_tmp_active" / "ignored_temp.py").write_text(
        "def ignored_temp() -> None:\n    return None\n",
        encoding="utf-8",
    )

    graph = analyze_project(tmp_path)

    assert graph.scan_stats is not None
    assert graph.scan_stats.files_discovered == 3
    assert graph.scan_stats.files_parsed == 3
    assert {symbol.symbol_id for symbol in graph.symbols} == {
        "shop.pricing.total",
        "shop.checkout.Checkout",
        "shop.checkout.Checkout.run",
    }
    assert any(
        edge.kind is StaticFlowEdgeKind.ARG
        and edge.source_symbol_id == "shop.checkout.Checkout.run"
        and edge.target_symbol_id == "shop.pricing.total"
        and edge.source_slot == "price"
        and edge.target_slot == "price"
        for edge in graph.edges
    )
    assert "ignored" not in {symbol.symbol_id for symbol in graph.symbols}
    assert "ignored_temp" not in {symbol.symbol_id for symbol in graph.symbols}


def test_project_import_can_skip_large_files_and_extra_dirs(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        "def main() -> int:\n    return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "generated.py").write_text(
        "def generated() -> int:\n"
        f"    return {1}\n"
        + ("# generated\n" * 200),
        encoding="utf-8",
    )
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / "lib.py").write_text(
        "def lib() -> int:\n    return 2\n",
        encoding="utf-8",
    )

    graph = analyze_project(
        tmp_path,
        options=AnalyzeProjectOptions(
            excluded_dir_names=AnalyzeProjectOptions().excluded_dir_names | {"vendor"},
            max_file_size_kb=1,
            workers=2,
        ),
    )

    assert graph.scan_stats is not None
    assert graph.scan_stats.files_discovered == 1
    assert graph.scan_stats.files_parsed == 1
    assert graph.scan_stats.files_skipped == 2
    assert {symbol.symbol_id for symbol in graph.symbols} == {"main.main"}


def test_text_report_marks_unresolved_calls() -> None:
    graph = analyze_project(REPO_ROOT / "resources" / "fixtures" / "example.py")
    report = format_static_flow_report(graph)

    assert "Scan:" in report
    assert "Graph:" in report
    assert "[function] example.main" in report
    assert "arg: -> example.compute | 3 -> a" in report
    assert "unresolved_call: -> print | print(Calc.multiply(result, 2.0))" in report


def test_summary_report_is_project_level_not_edge_dump() -> None:
    graph = analyze_project(REPO_ROOT)
    summary = format_static_flow_summary(graph, symbol_limit=5)

    assert "Scan:" in summary
    assert "Graph:" in summary
    assert "Top-level files:" in summary
    assert "Symbols:" in summary
    assert "arg: ->" not in summary
    assert "Warnings:" not in summary
    assert "more symbols" in summary
