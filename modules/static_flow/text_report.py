from __future__ import annotations

from collections import defaultdict

from contracts.static_flow import StaticFlowEdgeKind, StaticProjectGraph, StaticSymbolKind


def format_static_flow_summary(graph: StaticProjectGraph, *, symbol_limit: int | None = 200) -> str:
    lines = _format_header(graph)
    lines.append("Top-level files:")
    file_counts: dict[str, int] = defaultdict(int)
    for symbol in graph.symbols:
        file_counts[symbol.file_path] += 1
    for file_path, count in sorted(file_counts.items(), key=lambda item: item[0]):
        lines.append(f"  {file_path}: {count} symbols")

    lines.append("")
    lines.append("Symbols:")
    visible_symbols = graph.symbols
    if symbol_limit is not None and symbol_limit >= 0:
        visible_symbols = graph.symbols[:symbol_limit]
    for symbol in visible_symbols:
        if symbol.kind is StaticSymbolKind.CLASS:
            lines.append(f"  [class] {symbol.qualified_name}")
            continue
        prefix = "[method]" if symbol.kind is StaticSymbolKind.METHOD else "[function]"
        lines.append(f"  {prefix} {symbol.qualified_name}")
    hidden_count = len(graph.symbols) - len(visible_symbols)
    if hidden_count > 0:
        lines.append(f"  ... {hidden_count} more symbols. Use --limit-symbols 0 for no limit.")

    if graph.warnings:
        lines.append("")
        lines.append(f"Warnings: {len(graph.warnings)}")
        for warning in graph.warnings[:10]:
            lines.append(f"  - {warning}")
        remaining = len(graph.warnings) - 10
        if remaining > 0:
            lines.append(f"  - ... {remaining} more")

    return "\n".join(lines).rstrip() + "\n"


def format_static_flow_report(graph: StaticProjectGraph) -> str:
    signatures = {signature.symbol_id: signature for signature in graph.signatures}
    locals_by_symbol = defaultdict(list)
    for variable in graph.local_variables:
        locals_by_symbol[variable.symbol_id].append(variable)

    edges_by_source = defaultdict(list)
    return_edges_by_target = defaultdict(list)
    for edge in graph.edges:
        if edge.kind is StaticFlowEdgeKind.RETURN and edge.target_symbol_id is not None:
            return_edges_by_target[edge.target_symbol_id].append(edge)
        else:
            edges_by_source[edge.source_symbol_id].append(edge)

    lines = _format_header(graph)
    lines.append("")
    for symbol in graph.symbols:
        if symbol.kind is StaticSymbolKind.CLASS:
            lines.append(f"[class] {symbol.qualified_name}")
            continue

        prefix = "[method]" if symbol.kind is StaticSymbolKind.METHOD else "[function]"
        method_suffix = f" ({symbol.method_kind.value})" if symbol.method_kind else ""
        lines.append(f"{prefix} {symbol.qualified_name}{method_suffix}")

        signature = signatures.get(symbol.symbol_id)
        if signature is not None:
            params = ", ".join(
                f"{param.name}: {param.type_annotation or 'Unknown'}"
                for param in signature.parameters
            )
            lines.append(f"  params: {params or 'none'}")
            lines.append(f"  returns: {signature.return_type or 'Unknown'}")

        variables = locals_by_symbol.get(symbol.symbol_id, [])
        if variables:
            rendered = ", ".join(variable.name for variable in variables)
            lines.append(f"  locals: {rendered}")

        outgoing = [
            edge
            for edge in edges_by_source.get(symbol.symbol_id, [])
            if edge.kind is not StaticFlowEdgeKind.CONTAINS
        ]
        incoming_returns = return_edges_by_target.get(symbol.symbol_id, [])
        if outgoing or incoming_returns:
            lines.append("  flow:")
            for edge in outgoing:
                target = edge.target_symbol_id or edge.target_slot or "unresolved"
                detail = f" | {edge.detail}" if edge.detail else ""
                lines.append(f"    {edge.kind.value}: -> {target}{detail}")
            for edge in incoming_returns:
                detail = f" | {edge.detail}" if edge.detail else ""
                lines.append(f"    return: {edge.source_symbol_id} -> {edge.target_slot}{detail}")
        lines.append("")

    if graph.warnings:
        lines.append("Warnings:")
        for warning in graph.warnings:
            lines.append(f"  - {warning}")

    return "\n".join(lines).rstrip() + "\n"


def _format_header(graph: StaticProjectGraph) -> list[str]:
    lines = [f"Project: {graph.project_root}"]
    if graph.scan_stats is not None:
        stats = graph.scan_stats
        lines.append(
            "Scan: "
            f"{stats.files_discovered} files discovered, "
            f"{stats.files_parsed} parsed, "
            f"{stats.files_failed} failed, "
            f"{stats.files_skipped} skipped, "
            f"{stats.elapsed_ms} ms"
        )
    lines.append(
        "Graph: "
        f"{len(graph.symbols)} symbols, "
        f"{len(graph.local_variables)} locals, "
        f"{len(graph.edges)} edges"
    )
    return lines
