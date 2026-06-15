from __future__ import annotations

from pathlib import Path

from contracts.static_flow import LanguageId, MethodKind, StaticFlowEdgeKind, StaticSymbolKind
from modules.static_flow import analyze_project


def test_typescript_adapter_resolves_named_imports_and_value_edges(tmp_path: Path) -> None:
    (tmp_path / "math.ts").write_text(
        "export function sum(a: number, b: number): number {\n"
        "  return a + b;\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "checkout.ts").write_text(
        "import { sum } from './math';\n\n"
        "export function checkout(price: number, count: number): number {\n"
        "  const total = sum(price, count);\n"
        "  return total;\n"
        "}\n",
        encoding="utf-8",
    )

    graph = analyze_project(tmp_path)

    assert any(symbol.language is LanguageId.TYPESCRIPT for symbol in graph.symbols)
    assert any(
        edge.kind is StaticFlowEdgeKind.CALL
        and edge.source_symbol_id == "checkout.checkout"
        and edge.target_symbol_id == "math.sum"
        for edge in graph.edges
    )
    assert any(
        edge.kind is StaticFlowEdgeKind.ARG
        and edge.source_slot == "price"
        and edge.target_slot == "a"
        for edge in graph.edges
    )
    assert any(
        edge.kind is StaticFlowEdgeKind.RETURN
        and edge.source_symbol_id == "math.sum"
        and edge.target_symbol_id == "checkout.checkout"
        and edge.target_slot == "total"
        for edge in graph.edges
    )


def test_tsx_adapter_extracts_class_methods_and_this_calls(tmp_path: Path) -> None:
    (tmp_path / "Widget.tsx").write_text(
        "export class Widget {\n"
        "  renderLabel(value: string): string {\n"
        "    return value;\n"
        "  }\n\n"
        "  render(): string {\n"
        "    const text = this.renderLabel('ok');\n"
        "    return text;\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )

    graph = analyze_project(tmp_path)
    symbols = {symbol.symbol_id: symbol for symbol in graph.symbols}

    assert symbols["Widget.Widget"].kind is StaticSymbolKind.CLASS
    assert symbols["Widget.Widget.render"].method_kind is MethodKind.INSTANCE
    assert any(
        edge.kind is StaticFlowEdgeKind.CALL
        and edge.source_symbol_id == "Widget.Widget.render"
        and edge.target_symbol_id == "Widget.Widget.renderLabel"
        for edge in graph.edges
    )
