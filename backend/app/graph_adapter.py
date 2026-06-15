from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from contracts.static_flow import (
    StaticFlowEdgeKind,
    StaticProjectGraph,
    StaticSignature,
    StaticSymbol,
    StaticSymbolKind,
)


SOURCE_FILE_SUFFIXES = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".go",
    ".rs",
    ".css",
    ".html",
    ".json",
    ".md",
    ".toml",
    ".yaml",
    ".yml",
}

EXCLUDED_TREE_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".beads",
    ".venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "history",
    "_archive",
}


def to_frontend_payload(graph: StaticProjectGraph) -> tuple[dict, dict[str, dict], str]:
    symbols_by_file: dict[str, list[StaticSymbol]] = defaultdict(list)
    symbol_by_id = {symbol.symbol_id: symbol for symbol in graph.symbols}
    signature_by_symbol_id = {signature.symbol_id: signature for signature in graph.signatures}
    local_vars_by_symbol_id = defaultdict(list)
    for variable in graph.local_variables:
        local_vars_by_symbol_id[variable.symbol_id].append(variable)

    for symbol in graph.symbols:
        symbols_by_file[symbol.file_path].append(symbol)

    nodes = []
    file_id_by_path: dict[str, str] = {}
    file_details: dict[str, dict] = {}

    for index, file_path in enumerate(sorted(symbols_by_file)):
        file_id = _file_node_id(file_path)
        file_id_by_path[file_path] = file_id
        symbols = sorted(symbols_by_file[file_path], key=lambda item: (item.start_line, item.symbol_id))
        functions = [
            _function_payload(symbol, signature_by_symbol_id.get(symbol.symbol_id))
            for symbol in symbols
            if symbol.kind is StaticSymbolKind.FUNCTION
        ]
        classes = [
            _class_payload(symbol, symbols, signature_by_symbol_id)
            for symbol in symbols
            if symbol.kind is StaticSymbolKind.CLASS
        ]
        imports, outputs = _ports_for_file(file_id, file_path, symbols, graph, symbol_by_id)
        relative_path = _relative_path(graph.project_root, file_path)
        node = {
            "id": file_id,
            "file_path": file_path,
            "file_name": Path(file_path).name,
            "folder_path": str(Path(relative_path).parent).replace("\\", "/")
            if str(Path(relative_path).parent) != "."
            else "",
            "language": _file_language(file_path, symbols),
            "summary": _file_summary(symbols),
            "detail": _file_detail(relative_path, symbols),
            "architecture_role": _guess_role(file_path, symbols),
            "ports": [*imports, *outputs],
            "functions": functions,
            "classes": classes,
            "x": (index % 4) * 320,
            "y": (index // 4) * 240,
        }
        nodes.append(node)
        file_details[file_id] = _file_analysis_detail(node, symbols, graph, local_vars_by_symbol_id)

    edges = []
    for edge in graph.edges:
        if edge.kind is StaticFlowEdgeKind.CONTAINS or edge.target_symbol_id is None:
            continue
        source = symbol_by_id.get(edge.source_symbol_id)
        target = symbol_by_id.get(edge.target_symbol_id)
        if source is None or target is None:
            continue
        source_node_id = file_id_by_path.get(source.file_path)
        target_node_id = file_id_by_path.get(target.file_path)
        if source_node_id is None or target_node_id is None:
            continue
        variable_name = _edge_variable_name(edge)
        edges.append(
            {
                "id": _safe_id(edge.edge_id),
                "source_node_id": source_node_id,
                "target_node_id": target_node_id,
                "source_port_id": f"out-{_safe_id(variable_name)}",
                "target_port_id": f"in-{_safe_id(edge.target_slot or target.display_name)}",
                "source_function_id": edge.source_symbol_id,
                "target_function_id": edge.target_symbol_id,
                "variable_name": variable_name,
                "data_type": _edge_data_type(edge, signature_by_symbol_id),
                "edge_type": edge.kind.value,
                "source_slot": edge.source_slot,
                "target_slot": edge.target_slot,
                "line_number": edge.line_number,
                "resolution": edge.resolution.value,
                "label": _edge_label(edge),
            }
        )

    entry_points = _entry_points(nodes, edges)
    exit_points = _exit_points(nodes, edges)
    payload = {"nodes": nodes, "edges": edges, "entry_points": entry_points, "exit_points": exit_points}
    payload["project_files"] = _project_file_payloads(graph.project_root, symbols_by_file, file_id_by_path)
    return payload, file_details, _report_markdown(graph, payload)


def _function_payload(symbol: StaticSymbol, signature: StaticSignature | None) -> dict:
    params = []
    if signature is not None:
        params = [
            {"name": param.name, "type": param.type_annotation or "Unknown"}
            for param in signature.parameters
        ]
    return {
        "id": symbol.symbol_id,
        "name": symbol.display_name.rsplit(".", maxsplit=1)[-1],
        "qualified_name": symbol.qualified_name,
        "start_line": symbol.start_line,
        "end_line": symbol.end_line,
        "params": params,
        "return_type": signature.return_type if signature and signature.return_type else "Unknown",
        "is_exported": not symbol.display_name.startswith("_"),
        "is_async": False,
        "description": f"{symbol.qualified_name} at line {symbol.start_line}",
    }


def _class_payload(
    class_symbol: StaticSymbol,
    file_symbols: list[StaticSymbol],
    signature_by_symbol_id: dict[str, StaticSignature],
) -> dict:
    methods = [
        _function_payload(symbol, signature_by_symbol_id.get(symbol.symbol_id))
        for symbol in file_symbols
        if symbol.parent_symbol_id == class_symbol.symbol_id and symbol.kind is StaticSymbolKind.METHOD
    ]
    return {
        "id": class_symbol.symbol_id,
        "name": class_symbol.display_name,
        "qualified_name": class_symbol.qualified_name,
        "start_line": class_symbol.start_line,
        "end_line": class_symbol.end_line,
        "is_exported": not class_symbol.display_name.startswith("_"),
        "methods": methods,
    }


def _ports_for_file(
    file_id: str,
    file_path: str,
    symbols: list[StaticSymbol],
    graph: StaticProjectGraph,
    symbol_by_id: dict[str, StaticSymbol],
) -> tuple[list[dict], list[dict]]:
    symbol_ids = {symbol.symbol_id for symbol in symbols}
    input_names: set[str] = set()
    output_names: set[str] = set()
    for edge in graph.edges:
        if edge.kind is StaticFlowEdgeKind.CONTAINS:
            continue
        source_in_file = edge.source_symbol_id in symbol_ids
        target_in_file = edge.target_symbol_id in symbol_ids if edge.target_symbol_id else False
        if target_in_file and edge.source_symbol_id not in symbol_ids:
            source = symbol_by_id.get(edge.source_symbol_id)
            input_names.add(source.display_name if source else edge.source_slot or "input")
        if source_in_file and edge.target_symbol_id and edge.target_symbol_id not in symbol_ids:
            target = symbol_by_id.get(edge.target_symbol_id)
            output_names.add(target.display_name if target else edge.target_slot or "output")

    inputs = [
        _port_payload(file_id, "input", name, index)
        for index, name in enumerate(sorted(input_names))
    ]
    outputs = [
        _port_payload(file_id, "output", name, index)
        for index, name in enumerate(sorted(output_names))
    ]
    if not outputs:
        exported = [symbol.display_name for symbol in symbols if symbol.parent_symbol_id is None]
        outputs = [
            _port_payload(file_id, "output", name, index)
            for index, name in enumerate(sorted(exported)[:8])
        ]
    return inputs, outputs


def _port_payload(file_id: str, direction: str, name: str, index: int) -> dict:
    prefix = "in" if direction == "input" else "out"
    return {
        "id": f"{prefix}-{_safe_id(name)}-{index}",
        "name": name,
        "port_type": "function",
        "data_type": "Unknown",
        "direction": direction,
        "description": name,
    }


def _file_analysis_detail(
    node: dict,
    symbols: list[StaticSymbol],
    graph: StaticProjectGraph,
    local_vars_by_symbol_id: dict,
) -> dict:
    inputs = [
        {
            "name": port["name"],
            "type": port["data_type"],
            "source": "cross-file call",
            "is_function": True,
            "description": port["description"],
        }
        for port in node["ports"]
        if port["direction"] == "input"
    ]
    outputs = [
        {
            "name": symbol.display_name,
            "type": symbol.kind.value,
            "source": symbol.file_path,
            "is_function": symbol.kind is not StaticSymbolKind.CLASS,
            "description": f"{symbol.qualified_name} lines {symbol.start_line}-{symbol.end_line}",
        }
        for symbol in symbols
        if symbol.parent_symbol_id is None
    ]
    internal_structures = []
    for symbol in symbols:
        variables = local_vars_by_symbol_id.get(symbol.symbol_id, [])
        if variables:
            internal_structures.append(
                {
                    "name": symbol.display_name,
                    "type": symbol.kind.value,
                    "fields": [
                        {
                            "name": variable.name,
                            "type": variable.type_annotation or "Unknown",
                            "value": variable.value_preview or "",
                        }
                        for variable in variables[:20]
                    ],
                }
            )
    return {
        "file_path": node["file_path"],
        "summary": node["summary"],
        "detail": node["detail"],
        "inputs": inputs,
        "outputs": outputs,
        "internal_structures": internal_structures,
        "architecture_role": node["architecture_role"],
        "dependencies_summary": _dependencies_summary(node["id"], graph, node["file_path"]),
    }


def _dependencies_summary(file_id: str, graph: StaticProjectGraph, file_path: str) -> str:
    return f"Static symbols from {Path(file_path).name}; cross-file links are based on resolved calls."


def _file_summary(symbols: list[StaticSymbol]) -> str:
    functions = sum(1 for symbol in symbols if symbol.kind is StaticSymbolKind.FUNCTION)
    classes = sum(1 for symbol in symbols if symbol.kind is StaticSymbolKind.CLASS)
    methods = sum(1 for symbol in symbols if symbol.kind is StaticSymbolKind.METHOD)
    return f"{functions} functions, {classes} classes, {methods} methods"


def _file_detail(relative_path: str, symbols: list[StaticSymbol]) -> str:
    names = ", ".join(symbol.display_name for symbol in symbols[:8])
    if len(symbols) > 8:
        names += f", +{len(symbols) - 8} more"
    return f"{relative_path}: {names}" if names else relative_path


def _guess_role(file_path: str, symbols: list[StaticSymbol]) -> str:
    lower = file_path.replace("\\", "/").lower()
    if "test" in lower:
        return "test"
    if "api" in lower or "route" in lower:
        return "api"
    if "model" in lower or "schema" in lower or any(s.kind is StaticSymbolKind.CLASS for s in symbols):
        return "model"
    if "service" in lower or "analyzer" in lower:
        return "service"
    if "util" in lower or "helper" in lower:
        return "utility"
    return "module"


def _file_language(file_path: str, symbols: list[StaticSymbol]) -> str:
    languages = {symbol.language.value for symbol in symbols}
    if len(languages) == 1:
        return next(iter(languages))
    return _language_from_suffix(Path(file_path).suffix)


def _edge_variable_name(edge) -> str:
    if edge.kind is StaticFlowEdgeKind.ARG:
        return edge.source_slot or edge.target_slot or "arg"
    if edge.kind is StaticFlowEdgeKind.RETURN:
        return edge.target_slot or "return"
    return edge.source_slot or edge.target_slot or "call"


def _edge_data_type(edge, signature_by_symbol_id: dict[str, StaticSignature]) -> str:
    if edge.kind is StaticFlowEdgeKind.RETURN:
        signature = signature_by_symbol_id.get(edge.source_symbol_id)
        return signature.return_type if signature and signature.return_type else "Unknown"
    return "Unknown"


def _edge_label(edge) -> str:
    if edge.detail:
        return edge.detail
    return edge.kind.value


def _entry_points(nodes: list[dict], edges: list[dict]) -> list[str]:
    targets = {edge["target_node_id"] for edge in edges}
    return [node["id"] for node in nodes if node["id"] not in targets]


def _exit_points(nodes: list[dict], edges: list[dict]) -> list[str]:
    sources = {edge["source_node_id"] for edge in edges}
    return [node["id"] for node in nodes if node["id"] not in sources]


def _report_markdown(graph: StaticProjectGraph, payload: dict) -> str:
    stats = graph.scan_stats
    lines = [
        "# Project Analysis Report",
        "",
        f"- Project root: `{graph.project_root}`",
        f"- Files parsed: {stats.files_parsed if stats else len(payload['nodes'])}",
        f"- Symbols: {len(graph.symbols)}",
        f"- Edges: {len(graph.edges)}",
        f"- Warnings: {len(graph.warnings)}",
        "",
        "## Files",
        "",
    ]
    for node in payload["nodes"]:
        lines.append(f"- `{node['file_path']}`: {node['summary']}")
    if graph.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in graph.warnings)
    return "\n".join(lines)


def _relative_path(project_root: str, file_path: str) -> str:
    try:
        return str(Path(file_path).resolve().relative_to(Path(project_root).resolve()))
    except ValueError:
        return file_path


def _file_node_id(file_path: str) -> str:
    return f"file:{_safe_id(file_path)}"


def _safe_id(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)
    return safe[:180]


def _project_file_payloads(
    project_root: str,
    symbols_by_file: dict[str, list[StaticSymbol]],
    file_id_by_path: dict[str, str],
) -> list[dict]:
    root = Path(project_root).resolve()
    if not root.exists():
        return []

    symbol_count_by_resolved_path = {
        str(Path(file_path).resolve()): len(symbols)
        for file_path, symbols in symbols_by_file.items()
    }
    file_id_by_resolved_path = {
        str(Path(file_path).resolve()): file_id
        for file_path, file_id in file_id_by_path.items()
    }
    files: list[dict] = []
    for path in sorted(root.rglob("*")):
        if len(files) >= 2500:
            break
        if not path.is_file() or path.suffix.lower() not in SOURCE_FILE_SUFFIXES:
            continue
        try:
            relative_path = path.resolve().relative_to(root)
        except ValueError:
            continue
        if any(part in EXCLUDED_TREE_DIR_NAMES or part.startswith(".") for part in relative_path.parts[:-1]):
            continue
        resolved = str(path.resolve())
        folder = str(relative_path.parent).replace("\\", "/")
        symbol_count = symbol_count_by_resolved_path.get(resolved, 0)
        files.append(
            {
                "id": file_id_by_resolved_path.get(resolved, _file_node_id(resolved)),
                "file_path": resolved,
                "file_name": path.name,
                "folder_path": "" if folder == "." else folder,
                "language": _language_from_suffix(path.suffix),
                "has_symbols": symbol_count > 0,
                "symbol_count": symbol_count,
            }
        )
    return files


def _language_from_suffix(suffix: str) -> str:
    return {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".css": "css",
        ".html": "html",
        ".json": "json",
        ".md": "markdown",
        ".toml": "toml",
        ".yaml": "yaml",
        ".yml": "yaml",
    }.get(suffix.lower(), "text")
