from __future__ import annotations

from contracts.static_flow import (
    StaticFlowEdgeKind,
    StaticProjectGraph,
    StaticSymbol,
    StaticSymbolKind,
)


def export_static_flow_dot(graph: StaticProjectGraph) -> str:
    symbols_by_id = {symbol.symbol_id: symbol for symbol in graph.symbols}
    lines = [
        "digraph static_flow {",
        '  graph [rankdir="TB"];',
        '  node [shape="box", style="rounded,filled", fillcolor="#fff7cc"];',
        '  edge [fontname="Arial"];',
    ]

    for symbol in graph.symbols:
        if symbol.kind is StaticSymbolKind.METHOD:
            continue
        lines.append(_dot_node(symbol))

    for symbol in graph.symbols:
        if symbol.kind is not StaticSymbolKind.METHOD:
            continue
        parent = symbols_by_id.get(symbol.parent_symbol_id or "")
        if parent is None:
            lines.append(_dot_node(symbol))
            continue
        lines.append(_dot_node(symbol))

    external_count = 0
    for edge in graph.edges:
        if edge.kind is StaticFlowEdgeKind.CONTAINS:
            continue
        source_id = _quote(edge.source_symbol_id)
        if edge.target_symbol_id is None:
            external_count += 1
            target_id = _quote(f"external_{external_count}")
            label = edge.target_slot or "unresolved"
            lines.append(
                f"  {target_id} [label={_quote(label)}, style=\"dashed,filled\", "
                'fillcolor="#eeeeee"];'
            )
        else:
            target_id = _quote(edge.target_symbol_id)
        lines.append(
            f"  {source_id} -> {target_id} "
            f"[label={_quote(_edge_label(edge.kind.value, edge.detail))}];"
        )

    lines.append("}")
    return "\n".join(lines) + "\n"


def _dot_node(symbol: StaticSymbol) -> str:
    label_parts = [symbol.display_name, symbol.kind.value]
    if symbol.method_kind is not None:
        label_parts.append(symbol.method_kind.value)
    label = "\\n".join(label_parts)
    fill = "#dff2ff" if symbol.kind is StaticSymbolKind.CLASS else "#fff7cc"
    return f"  {_quote(symbol.symbol_id)} [label={_quote(label)}, fillcolor={_quote(fill)}];"


def _edge_label(kind: str, detail: str | None) -> str:
    if detail:
        return f"{kind}: {detail}"
    return kind


def _quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
