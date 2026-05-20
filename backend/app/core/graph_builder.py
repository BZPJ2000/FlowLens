"""Phase 1: 关系构建引擎 — 将所有文件的分析结果组装成数据流图

核心职责:
1. 文件 → 图节点（带输入/输出端口）
2. import/export 匹配 → 图边（跨模块模糊匹配）
3. 循环依赖检测（DFS 回溯）
4. 未使用导出检测
5. 入口/出口文件识别
"""

import hashlib
import posixpath
from collections import defaultdict
from pathlib import Path

from app.models.schemas import (
    AIFileAnalysis,
    DataFlowGraph,
    EdgeType,
    FunctionNode,
    GraphEdge,
    GraphNode,
    GraphPort,
    ParseResult,
)


# ── Deterministic ID helpers ──────────────────

def make_fn_id(file_path: str, fn_name: str) -> str:
    """Generate deterministic function ID from file path + function name"""
    h = hashlib.md5(f"{file_path}::fn::{fn_name}".encode()).hexdigest()[:24]
    return f"fn_{h}"

def make_class_id(file_path: str, class_name: str) -> str:
    """Generate deterministic class ID from file path + class name"""
    h = hashlib.md5(f"{file_path}::cls::{class_name}".encode()).hexdigest()[:24]
    return f"cls_{h}"

def make_method_id(file_path: str, class_name: str, method_name: str) -> str:
    """Generate deterministic method ID"""
    h = hashlib.md5(f"{file_path}::cls::{class_name}::m::{method_name}".encode()).hexdigest()[:24]
    return f"m_{h}"


SOURCE_EXTS = (
    ".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rs", ".java",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".swift", ".kt",
    ".vue", ".svelte",
)


def make_port_id(direction: str, name: str) -> str:
    return f"port-{direction}-{name}"


def _param_name(param) -> str:
    if isinstance(param, dict):
        return str(param.get("name", ""))
    return str(getattr(param, "name", ""))


def _param_type(param) -> str:
    if isinstance(param, dict):
        return str(param.get("type", "unknown") or "unknown")
    return str(getattr(param, "type", "unknown") or "unknown")


def _strip_source_ext(value: str) -> str:
    lower = value.lower()
    for ext in SOURCE_EXTS:
        if lower.endswith(ext):
            return value[: -len(ext)]
    return value


def _path_candidates(value: str) -> set[str]:
    normalized = _strip_source_ext(value.replace("\\", "/").strip("/"))
    candidates = {normalized}
    if normalized.endswith("/index"):
        candidates.add(normalized[: -len("/index")])
    return {c for c in candidates if c and c != "."}


def _module_candidates(source_module: str, importer_path: str) -> set[str]:
    clean = source_module.strip().strip("\"'").replace("\\", "/")
    clean = clean.split("?", 1)[0].split("#", 1)[0]
    if not clean or clean == "(dynamic)":
        return set()

    importer_dir = posixpath.dirname(importer_path.replace("\\", "/"))
    raw_variants: set[str] = set()
    if clean.startswith("."):
        raw_variants.add(posixpath.normpath(posixpath.join(importer_dir, clean)))
    else:
        raw_variants.add(clean.lstrip("/"))
        raw_variants.add(clean.replace(".", "/").lstrip("/"))

    candidates: set[str] = set()
    for variant in raw_variants:
        candidates.update(_path_candidates(variant))
    return candidates


def module_matches_path(source_module: str, importer_path: str, export_path: str) -> bool:
    module_candidates = _module_candidates(source_module, importer_path)
    export_candidates = _path_candidates(export_path)
    for module_path in module_candidates:
        for export_candidate in export_candidates:
            if module_path == export_candidate or export_candidate.endswith(f"/{module_path}"):
                return True
    return False


# ── 循环依赖检测 ─────────────────────────────

def detect_cycles(edges: list[GraphEdge]) -> list[list[str]]:
    """用 DFS 回溯检测图中的所有简单环（节点数 ≤ 10 的环）"""
    adj: dict[str, list[str]] = defaultdict(list)
    node_ids = set()
    for e in edges:
        adj[e.source_node_id].append(e.target_node_id)
        node_ids.add(e.source_node_id)
        node_ids.add(e.target_node_id)

    cycles: list[list[str]] = []
    visited: set[str] = set()
    stack: list[str] = []

    def _dfs(node: str):
        if node in stack:
            cycle_start = stack.index(node)
            cycle = stack[cycle_start:] + [node]
            if 2 <= len(cycle) <= 10:
                cycles.append(cycle)
            return
        if node in visited:
            return
        visited.add(node)
        stack.append(node)
        for neighbor in adj.get(node, []):
            _dfs(neighbor)
        stack.pop()

    for nid in list(node_ids):
        visited.clear()
        stack.clear()
        _dfs(nid)

    # 去重（同一个环的不同旋转视为重复）
    unique = []
    seen = set()
    for c in cycles:
        key = tuple(sorted(c[:-1]))
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


# ── 图构建器 ─────────────────────────────────

class GraphBuilder:
    """根据 AI 分析结果 + Parse 结果构建数据流图"""

    def build(
        self,
        parse_results: list[ParseResult],
        ai_results: list[AIFileAnalysis],
    ) -> DataFlowGraph:
        ai_map: dict[str, AIFileAnalysis] = {a.file_path: a for a in ai_results}

        # Step 1: 创建节点
        nodes: list[GraphNode] = []
        node_by_path: dict[str, GraphNode] = {}
        node_by_file: dict[str, GraphNode] = {}  # 仅文件名 → 节点

        for parse in parse_results:
            ai = ai_map.get(parse.file_path)
            node = self._build_node(parse, ai)
            nodes.append(node)
            node_by_path[parse.file_path] = node
            # 文件名索引用于模糊匹配
            stem = Path(parse.file_path).stem
            node_by_file[stem] = node
            # 也索引不含扩展名的相对路径
            rel_noext = str(Path(parse.file_path).with_suffix(""))
            node_by_file[rel_noext] = node

        # Step 2: 构建边（多策略匹配）
        edges = self._build_edges(
            parse_results, ai_map, node_by_path, node_by_file
        )

        # Step 2.5: 构建端口→函数参数级边
        param_edges = self._build_port_to_param_edges(nodes, parse_results)
        edges.extend(param_edges)
        call_edges = self._build_internal_call_edges(nodes, parse_results)
        edges.extend(call_edges)
        cross_call_edges = self._build_cross_file_call_edges(nodes, parse_results, node_by_path, node_by_file)
        edges.extend(cross_call_edges)
        edges = self._dedupe_edges(edges)

        # Step 3: 识别入口/出口
        entry_points, exit_points = self._identify_endpoints(nodes, edges, ai_map)

        # Step 4: 循环依赖检测
        cycles = detect_cycles(edges)

        # Step 5: 未使用导出检测
        unused_exports = self._detect_unused_exports(nodes, edges)

        return DataFlowGraph(
            nodes=nodes,
            edges=edges,
            entry_points=entry_points,
            exit_points=exit_points,
            cycles=cycles,
            unused_exports=unused_exports,
        )

    # ── 节点构建 ─────────────────────────────

    def _build_node(
        self,
        parse: ParseResult,
        ai: AIFileAnalysis | None,
    ) -> GraphNode:
        ports: list[GraphPort] = []
        port_keys: set[tuple[str, str]] = set()

        def add_port(name: str, port_type: str, data_type: str, direction: str, description: str = ""):
            if not name:
                return
            key = (direction, name)
            if key in port_keys:
                return
            port_keys.add(key)
            ports.append(GraphPort(
                id=make_port_id(direction, name),
                name=name,
                port_type=port_type,
                data_type=data_type or "unknown",
                direction=direction,
                description=description,
            ))

        if ai:
            for inp in ai.inputs:
                add_port(
                    inp.name,
                    "function" if inp.is_function else "variable",
                    inp.type,
                    "input",
                    inp.description,
                )
        else:
            for imp in parse.imports:
                add_port(imp.variable_name, "variable", imp.data_type, "input")

        if ai:
            for out in ai.outputs:
                add_port(
                    out.name,
                    "function" if out.is_function else "variable",
                    out.type,
                    "output",
                    out.description,
                )
        else:
            for exp in parse.exports:
                add_port(
                    exp.variable_name,
                    "function" if exp.is_function else "variable",
                    exp.data_type,
                    "output",
                )

        # Build function nodes from parsed function signatures
        functions: list[FunctionNode] = []
        exported_names = {e.variable_name for e in parse.exports}
        for fn in parse.functions:
            fn_desc = ""
            if ai and ai.internal_structures:
                for s in ai.internal_structures:
                    if isinstance(s, dict) and s.get("name") == fn.name:
                        fn_desc = str(s.get("description", ""))
                        break
            functions.append(FunctionNode(
                id=make_fn_id(parse.file_path, fn.name),
                name=fn.name,
                params=fn.params if fn.params else [],
                return_type=fn.return_type,
                is_exported=fn.is_exported or fn.name in exported_names,
                is_async=fn.is_async,
                description=fn_desc,
            ))

        for fn in parse.functions:
            for param in fn.params or []:
                add_port(_param_name(param), "param", _param_type(param), "input", f"{fn.name}() 参数")
        for cls in parse.classes or []:
            for method in cls.methods or []:
                for param in method.params or []:
                    add_port(_param_name(param), "param", _param_type(param), "input", f"{cls.name}.{method.name}() 参数")

        return GraphNode(
            file_path=parse.file_path,
            file_name=parse.file_name,
            language=parse.language,
            summary=ai.summary if ai else "",
            detail=ai.detail if ai else "",
            architecture_role=ai.architecture_role if ai else "",
            ports=ports,
            functions=functions,
        )

    # ── 边构建（多策略匹配）─────────────────

    def _build_edges(
        self,
        parse_results: list[ParseResult],
        ai_map: dict[str, AIFileAnalysis],
        node_by_path: dict[str, GraphNode],
        node_by_file: dict[str, GraphNode],
    ) -> list[GraphEdge]:
        edges: list[GraphEdge] = []

        # 建立全局导出索引: {变量名 → [(文件路径, 类型, port_id)]}
        export_index: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
        for parse in parse_results:
            ai = ai_map.get(parse.file_path)
            if ai:
                for out in ai.outputs:
                    node = node_by_path.get(parse.file_path)
                    port_id = self._find_port_id(node, out.name, "output") if node else ""
                    export_index[out.name].append((parse.file_path, out.type, port_id))
            else:
                for exp in parse.exports:
                    node = node_by_path.get(parse.file_path)
                    port_id = self._find_port_id(node, exp.variable_name, "output") if node else ""
                    export_index[exp.variable_name].append(
                        (parse.file_path, exp.data_type, port_id)
                    )

        # 匹配每个文件的 import
        for parse in parse_results:
            target_node = node_by_path.get(parse.file_path)
            if not target_node:
                continue

            ai = ai_map.get(parse.file_path)
            imports_to_match: list[tuple[str, list[str], str, str]] = []

            if ai:
                for inp in ai.inputs:
                    imports_to_match.append(
                        (inp.name, [inp.name], inp.source, inp.type)
                    )
            else:
                for imp in parse.imports:
                    match_names = [imp.variable_name]
                    if imp.alias and imp.alias not in match_names:
                        match_names.append(imp.alias)
                    imports_to_match.append(
                        (imp.variable_name, match_names, imp.source_module, imp.data_type)
                    )

            for var_name, match_names, source_module, data_type in imports_to_match:
                candidates = [
                    candidate
                    for match_name in match_names
                    for candidate in export_index.get(match_name, [])
                ]
                matched = False

                # 策略1: 精确匹配 source_module → 文件路径
                if source_module:
                    for export_path, export_type, source_port_id in candidates:
                        if module_matches_path(source_module, parse.file_path, export_path):
                            source_node = node_by_path.get(export_path)
                            if source_node and source_node.id != target_node.id:
                                target_port_id = self._find_port_id(
                                    target_node, var_name, "input"
                                )
                                edges.append(GraphEdge(
                                    source_node_id=source_node.id,
                                    target_node_id=target_node.id,
                                    source_port_id=source_port_id,
                                    target_port_id=target_port_id,
                                    variable_name=var_name,
                                    data_type=export_type or data_type,
                                    edge_type=EdgeType.IMPORT,
                                    label=f"{var_name}: {export_type or data_type}",
                                ))
                                matched = True
                                break

                # 策略2: 模糊匹配（文件名包含关系）
                if not matched and source_module:
                    module_names = _module_candidates(source_module, parse.file_path)
                    source_stems = {Path(m).name.lower() for m in module_names}
                    for export_path, export_type, source_port_id in candidates:
                        export_lower = Path(export_path).stem.lower()
                        source_node = node_by_path.get(export_path)
                        if not source_node or source_node.id == target_node.id:
                            continue
                        # 检查文件名是否互相包含
                        if any(
                            source_lower in export_lower or
                            export_lower in source_lower or
                            source_lower.replace("_", "") == export_lower.replace("_", "")
                            for source_lower in source_stems
                        ):
                            target_port_id = self._find_port_id(
                                target_node, var_name, "input"
                            )
                            edges.append(GraphEdge(
                                source_node_id=source_node.id,
                                target_node_id=target_node.id,
                                source_port_id=source_port_id,
                                target_port_id=target_port_id,
                                variable_name=var_name,
                                data_type=export_type or data_type,
                                edge_type=EdgeType.IMPORT,
                                label=f"{var_name}: {export_type or data_type}",
                            ))
                            matched = True
                            break

                # 策略3: 纯变量名匹配（无 source 信息时）
                if not matched:
                    for export_path, export_type, source_port_id in candidates:
                        source_node = node_by_path.get(export_path)
                        if source_node and source_node.id != target_node.id:
                            target_port_id = self._find_port_id(
                                target_node, var_name, "input"
                            )
                            edges.append(GraphEdge(
                                source_node_id=source_node.id,
                                target_node_id=target_node.id,
                                source_port_id=source_port_id,
                                target_port_id=target_port_id,
                                variable_name=var_name,
                                data_type=export_type or data_type,
                                edge_type=EdgeType.IMPORT,
                                label=f"{var_name}: {export_type or data_type}",
                            ))
                            break

        return edges

    # ── 端口→函数参数级边 ────────────────────

    def _build_port_to_param_edges(
        self,
        nodes: list[GraphNode],
        parse_results: list[ParseResult],
    ) -> list[GraphEdge]:
        """为每个文件的输入端口匹配内部函数参数，生成 port_to_function 边。

        逻辑：如果文件有输入端口 port.name == X，且文件内某函数有参数名 == X，
        则创建一条 port_to_function 边，variable_name=X，连到该函数的具体参数。
        """
        import uuid as _uuid
        edges: list[GraphEdge] = []
        parse_by_path = {p.file_path: p for p in parse_results}

        for node in nodes:
            input_ports = [p for p in node.ports if p.direction == "input"]
            if not input_ports:
                continue

            for port in input_ports:
                # 查找哪些函数的参数名匹配这个端口
                for fn in node.functions:
                    for param in (fn.params or []):
                        param_name = _param_name(param)
                        if param_name == port.name:
                            edges.append(GraphEdge(
                                id=str(_uuid.uuid4()),
                                source_node_id=node.id,
                                target_node_id=node.id,
                                source_port_id=port.id,
                                target_port_id="",
                                source_function_id="",
                                target_function_id=fn.id,
                                variable_name=port.name,
                                data_type=port.data_type,
                                edge_type=EdgeType.PORT_TO_FUNCTION,
                                label=f"{port.name} → {fn.name}({param_name})",
                            ))
                parse = parse_by_path.get(node.file_path)
                if parse:
                    for cls in parse.classes or []:
                        for method in cls.methods or []:
                            for param in method.params or []:
                                param_name = _param_name(param)
                                if param_name == port.name:
                                    method_id = make_method_id(node.file_path, cls.name, method.name)
                                    edges.append(GraphEdge(
                                        id=str(_uuid.uuid4()),
                                        source_node_id=node.id,
                                        target_node_id=node.id,
                                        source_port_id=port.id,
                                        target_port_id="",
                                        source_function_id="",
                                        target_function_id=method_id,
                                        variable_name=port.name,
                                        data_type=port.data_type,
                                        edge_type=EdgeType.PORT_TO_FUNCTION,
                                        label=f"{port.name} → {cls.name}.{method.name}({param_name})",
                                    ))

        # 反向：函数输出 → 文件输出端口
        for node in nodes:
            output_ports = [p for p in node.ports if p.direction == "output"]
            if not output_ports or not node.functions:
                continue

            for port in output_ports:
                # 如果端口名匹配某个函数名，说明该函数的返回值就是这个输出
                for fn in node.functions:
                    if fn.name == port.name and fn.is_exported:
                        edges.append(GraphEdge(
                            id=str(_uuid.uuid4()),
                            source_node_id=node.id,
                            target_node_id=node.id,
                            source_port_id="",
                            target_port_id=port.id,
                            source_function_id=fn.id,
                            target_function_id="",
                            variable_name=fn.name,
                            data_type=fn.return_type or port.data_type,
                            edge_type=EdgeType.FUNCTION_TO_PORT,
                            label=f"{fn.name}() → {port.name}",
                        ))

        return edges

    def _build_internal_call_edges(
        self,
        nodes: list[GraphNode],
        parse_results: list[ParseResult],
    ) -> list[GraphEdge]:
        """Create one intra-file edge per argument passed between known functions."""
        import uuid as _uuid

        edges: list[GraphEdge] = []
        node_by_path = {n.file_path: n for n in nodes}
        fn_ids_by_path: dict[str, dict[str, str]] = {}
        fn_params_by_path: dict[str, dict[str, list[dict]]] = {}

        for node in nodes:
            ids = {fn.name: fn.id for fn in node.functions}
            params = {fn.name: fn.params or [] for fn in node.functions}
            fn_ids_by_path[node.file_path] = ids
            fn_params_by_path[node.file_path] = params

        # Also index class methods for intra-file call edges
        parse_by_path = {p.file_path: p for p in parse_results}
        for parse in parse_results:
            ids = fn_ids_by_path.setdefault(parse.file_path, {})
            params = fn_params_by_path.setdefault(parse.file_path, {})
            for cls in parse.classes or []:
                for method in cls.methods or []:
                    method_id = make_method_id(parse.file_path, cls.name, method.name)
                    ids[method.name] = method_id
                    params[method.name] = method.params or []

        for parse in parse_results:
            node = node_by_path.get(parse.file_path)
            if not node:
                continue
            fn_ids = fn_ids_by_path.get(parse.file_path, {})
            fn_params = fn_params_by_path.get(parse.file_path, {})

            for call in parse.calls or []:
                source_fn_id = fn_ids.get(call.caller_name)
                target_fn_id = fn_ids.get(call.callee_name)
                if not source_fn_id or not target_fn_id or source_fn_id == target_fn_id:
                    continue

                target_params = fn_params.get(call.callee_name, [])
                for idx, arg in enumerate(call.args or []):
                    arg_name = str(arg.get("name", ""))
                    if not arg_name:
                        continue
                    target_param_name = ""
                    if idx < len(target_params):
                        target_param_name = _param_name(target_params[idx])
                    variable_name = target_param_name or arg_name
                    edges.append(GraphEdge(
                        id=str(_uuid.uuid4()),
                        source_node_id=node.id,
                        target_node_id=node.id,
                        source_port_id="",
                        target_port_id="",
                        source_function_id=source_fn_id,
                        target_function_id=target_fn_id,
                        variable_name=variable_name,
                        data_type=str(arg.get("type", "unknown") or "unknown"),
                        edge_type=EdgeType.CALL,
                        label=f"{arg_name} → {call.callee_name}({variable_name})",
                    ))

        return edges

    def _build_cross_file_call_edges(
        self,
        nodes: list[GraphNode],
        parse_results: list[ParseResult],
        node_by_path: dict[str, GraphNode],
        node_by_file: dict[str, GraphNode],
    ) -> list[GraphEdge]:
        """跨文件函数调用边 — 当 B 调用从 A 导入的函数时，为每个参数创建 CALL 边。"""
        import uuid as _uuid

        edges: list[GraphEdge] = []
        node_by_path_local = {n.file_path: n for n in nodes}

        # 建立每个文件的 {导入变量名 → (源文件路径, 源函数原名)} 映射
        import_source_map: dict[str, dict[str, tuple[str, str]]] = {}
        for parse in parse_results:
            file_imports: dict[str, tuple[str, str]] = {}
            for imp in parse.imports:
                var_name = imp.variable_name
                if not var_name or not imp.source_module:
                    continue
                # 尝试匹配源文件
                for other_parse in parse_results:
                    if other_parse.file_path == parse.file_path:
                        continue
                    if module_matches_path(imp.source_module, parse.file_path, other_parse.file_path):
                        # 确认源文件确实导出了这个名字（或别名匹配）
                        exported_names = {e.variable_name for e in other_parse.exports}
                        fn_names = {f.name for f in other_parse.functions}
                        # 检查导入名或别名是否匹配源文件的导出/函数
                        original_name = imp.alias or var_name
                        if original_name in exported_names or original_name in fn_names:
                            file_imports[var_name] = (other_parse.file_path, original_name)
                            break
                        elif var_name in exported_names or var_name in fn_names:
                            file_imports[var_name] = (other_parse.file_path, var_name)
                            break
            import_source_map[parse.file_path] = file_imports

        # 建立每个文件的 {函数名 → function_id} 映射
        fn_ids_by_path: dict[str, dict[str, str]] = {}
        fn_params_by_path: dict[str, dict[str, list]] = {}
        for node in nodes:
            ids = {fn.name: fn.id for fn in node.functions}
            params = {fn.name: fn.params or [] for fn in node.functions}
            fn_ids_by_path[node.file_path] = ids
            fn_params_by_path[node.file_path] = params
        # 也索引类方法
        for parse in parse_results:
            ids = fn_ids_by_path.setdefault(parse.file_path, {})
            params = fn_params_by_path.setdefault(parse.file_path, {})
            for cls in parse.classes or []:
                for method in cls.methods or []:
                    method_id = make_method_id(parse.file_path, cls.name, method.name)
                    ids[method.name] = method_id
                    params[method.name] = method.params or []

        # 遍历每个文件的 calls，找跨文件调用
        for parse in parse_results:
            caller_node = node_by_path_local.get(parse.file_path)
            if not caller_node:
                continue
            file_imports = import_source_map.get(parse.file_path, {})
            caller_fn_ids = fn_ids_by_path.get(parse.file_path, {})

            for call in parse.calls or []:
                callee_name = call.callee_name
                # 检查 callee 是否是从其他文件导入的
                import_info = file_imports.get(callee_name)
                if not import_info:
                    continue
                source_file, original_fn_name = import_info

                target_node = node_by_path_local.get(source_file)
                if not target_node or target_node.id == caller_node.id:
                    continue

                source_fn_id = caller_fn_ids.get(call.caller_name, "")
                # callee 在源文件中的函数 ID（使用原始名称）
                target_fn_ids = fn_ids_by_path.get(source_file, {})
                target_fn_id = target_fn_ids.get(original_fn_name, "")
                target_params = fn_params_by_path.get(source_file, {}).get(original_fn_name, [])

                if not source_fn_id:
                    continue

                # 为每个参数创建一条边
                for idx, arg in enumerate(call.args or []):
                    arg_name = str(arg.get("name", ""))
                    if not arg_name:
                        continue
                    # 匹配目标函数的参数名
                    target_param_name = ""
                    if idx < len(target_params):
                        target_param_name = _param_name(target_params[idx])
                    variable_name = target_param_name or arg_name

                    edges.append(GraphEdge(
                        id=str(_uuid.uuid4()),
                        source_node_id=caller_node.id,
                        target_node_id=target_node.id,
                        source_port_id="",
                        target_port_id="",
                        source_function_id=source_fn_id,
                        target_function_id=target_fn_id,
                        variable_name=variable_name,
                        data_type=str(arg.get("type", "unknown") or "unknown"),
                        edge_type=EdgeType.CALL,
                        label=f"{call.caller_name}() → {callee_name}({variable_name})",
                    ))

        return edges

    def _identify_endpoints(
        self,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
        ai_map: dict[str, AIFileAnalysis],
    ) -> tuple[list[str], list[str]]:
        in_degree: dict[str, int] = defaultdict(int)
        out_degree: dict[str, int] = defaultdict(int)
        node_ids = {n.id for n in nodes}

        for e in edges:
            out_degree[e.source_node_id] += 1
            in_degree[e.target_node_id] += 1

        entries: list[str] = []
        exits: list[str] = []

        for nid in node_ids:
            if in_degree[nid] == 0 and out_degree[nid] > 0:
                entries.append(nid)
            elif out_degree[nid] == 0 and in_degree[nid] > 0:
                exits.append(nid)

        # 如果没有明确入口，按导出数和 controller 角色选
        if not entries:
            scored = []
            for n in nodes:
                ai = ai_map.get(n.file_path)
                score = out_degree.get(n.id, 0)
                if ai and ai.architecture_role in ("controller", "route", "view"):
                    score += 5
                scored.append((n.id, score))
            scored.sort(key=lambda x: -x[1])
            entries = [s[0] for s in scored[:3]]

        return entries, exits

    def _dedupe_edges(self, edges: list[GraphEdge]) -> list[GraphEdge]:
        deduped: list[GraphEdge] = []
        seen: set[tuple[str, ...]] = set()
        for edge in edges:
            edge_type = edge.edge_type.value if hasattr(edge.edge_type, "value") else str(edge.edge_type)
            key = (
                edge.source_node_id,
                edge.target_node_id,
                edge.source_port_id,
                edge.target_port_id,
                edge.source_function_id,
                edge.target_function_id,
                edge.variable_name,
                edge.data_type,
                edge_type,
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(edge)
        return deduped

    # ── 未使用导出 ────────────────────────────

    def _detect_unused_exports(
        self, nodes: list[GraphNode], edges: list[GraphEdge]
    ) -> list[dict]:
        exported: dict[str, list[str]] = {}  # {变量名: [节点id]}
        imported: set[str] = set()

        for n in nodes:
            for p in n.ports:
                if p.direction == "output":
                    exported.setdefault(p.name, []).append(n.id)
                elif p.direction == "input":
                    imported.add(p.name)

        unused = []
        for name, node_ids in exported.items():
            if name not in imported and name != "default":
                unused.append({
                    "variable_name": name,
                    "node_ids": node_ids,
                })
        return unused

    # ── 端口查找 ──────────────────────────────

    def _find_port_id(
        self, node: GraphNode | None, name: str, direction: str
    ) -> str:
        if not node:
            return ""
        for port in node.ports:
            if port.name == name and port.direction == direction:
                return port.id
        return ""


# 单例
graph_builder = GraphBuilder()
