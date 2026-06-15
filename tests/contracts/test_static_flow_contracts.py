from __future__ import annotations

from contracts.static_flow import (
    LanguageId,
    MethodKind,
    StaticFlowEdge,
    StaticFlowEdgeKind,
    StaticLocalVariable,
    StaticParam,
    StaticProjectGraph,
    StaticScanStats,
    StaticResolution,
    StaticSignature,
    StaticSymbol,
    StaticSymbolKind,
)


def test_static_flow_contracts_round_trip_through_dicts() -> None:
    class_symbol = StaticSymbol(
        symbol_id="sample.Calc",
        language=LanguageId.PYTHON,
        kind=StaticSymbolKind.CLASS,
        qualified_name="sample.Calc",
        display_name="Calc",
        file_path="sample.py",
        start_line=1,
        end_line=4,
    )
    method_symbol = StaticSymbol(
        symbol_id="sample.Calc.multiply",
        language=LanguageId.PYTHON,
        kind=StaticSymbolKind.METHOD,
        qualified_name="sample.Calc.multiply",
        display_name="Calc.multiply",
        file_path="sample.py",
        start_line=3,
        end_line=4,
        parent_symbol_id=class_symbol.symbol_id,
        method_kind=MethodKind.STATIC,
    )
    signature = StaticSignature(
        symbol_id=method_symbol.symbol_id,
        parameters=(
            StaticParam(name="p", type_annotation="float"),
            StaticParam(name="q", type_annotation="float"),
        ),
        return_type="float",
    )
    variable = StaticLocalVariable(
        symbol_id="sample.main",
        name="result",
        line_number=8,
        value_preview="compute(3, 5)",
    )
    edge = StaticFlowEdge(
        edge_id="arg:sample.main:sample.Calc.multiply:9:0:p",
        kind=StaticFlowEdgeKind.ARG,
        source_symbol_id="sample.main",
        target_symbol_id=method_symbol.symbol_id,
        source_slot="result",
        target_slot="p",
        detail="result -> p",
        line_number=9,
        resolution=StaticResolution.RESOLVED,
    )
    graph = StaticProjectGraph(
        project_root="E:/workspace/sample",
        symbols=(class_symbol, method_symbol),
        signatures=(signature,),
        local_variables=(variable,),
        edges=(edge,),
        warnings=("runtime values require tracing",),
        scan_stats=StaticScanStats(
            target_path="E:/workspace/sample",
            files_discovered=2,
            files_parsed=2,
            files_skipped=1,
            elapsed_ms=3,
        ),
    )

    assert StaticProjectGraph.from_dict(graph.to_dict()) == graph
