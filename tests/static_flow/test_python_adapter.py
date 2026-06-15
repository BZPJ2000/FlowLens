from __future__ import annotations

from pathlib import Path

from contracts.static_flow import MethodKind, StaticFlowEdgeKind, StaticSymbolKind
from modules.static_flow import analyze_project


def test_python_adapter_extracts_method_kinds_and_signatures(tmp_path: Path) -> None:
    (tmp_path / "service.py").write_text(
        "class Service:\n"
        "    def run(self, value: int) -> int:\n"
        "        return self.normalize(value)\n\n"
        "    @classmethod\n"
        "    def build(cls, raw: str) -> 'Service':\n"
        "        return cls()\n\n"
        "    @staticmethod\n"
        "    def normalize(value: int) -> int:\n"
        "        return value\n",
        encoding="utf-8",
    )

    graph = analyze_project(tmp_path)
    symbols = {symbol.symbol_id: symbol for symbol in graph.symbols}
    signatures = {signature.symbol_id: signature for signature in graph.signatures}

    assert symbols["service.Service"].kind is StaticSymbolKind.CLASS
    assert symbols["service.Service.run"].method_kind is MethodKind.INSTANCE
    assert symbols["service.Service.build"].method_kind is MethodKind.CLASS
    assert symbols["service.Service.normalize"].method_kind is MethodKind.STATIC
    assert [param.name for param in signatures["service.Service.run"].parameters] == ["value"]
    assert [param.name for param in signatures["service.Service.build"].parameters] == ["raw"]


def test_python_adapter_tracks_keyword_args_returns_and_unresolved_calls(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "def format_total(amount: int, currency: str = 'USD') -> str:\n"
        "    return f'{amount} {currency}'\n\n"
        "def checkout(price: int) -> str:\n"
        "    label = format_total(amount=price, currency='EUR')\n"
        "    missing(label)\n"
        "    return label\n",
        encoding="utf-8",
    )

    graph = analyze_project(tmp_path)

    assert any(
        edge.kind is StaticFlowEdgeKind.ARG
        and edge.source_symbol_id == "app.checkout"
        and edge.target_symbol_id == "app.format_total"
        and edge.source_slot == "price"
        and edge.target_slot == "amount"
        for edge in graph.edges
    )
    assert any(
        edge.kind is StaticFlowEdgeKind.RETURN
        and edge.source_symbol_id == "app.format_total"
        and edge.target_symbol_id == "app.checkout"
        and edge.target_slot == "label"
        for edge in graph.edges
    )
    assert any(
        edge.kind is StaticFlowEdgeKind.UNRESOLVED_CALL
        and edge.source_symbol_id == "app.checkout"
        and edge.target_slot == "missing"
        for edge in graph.edges
    )
