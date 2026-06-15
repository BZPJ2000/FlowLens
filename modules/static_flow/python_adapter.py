from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from contracts.static_flow import (
    LanguageId,
    MethodKind,
    StaticFlowEdge,
    StaticFlowEdgeKind,
    StaticLocalVariable,
    StaticParam,
    StaticProjectGraph,
    StaticResolution,
    StaticSignature,
    StaticSymbol,
    StaticSymbolKind,
)

UNKNOWN = "Unknown"


@dataclass(frozen=True, kw_only=True)
class ParsedPythonModule:
    file_path: str
    source_text: str
    tree: ast.Module


def build_python_static_graph(
    project_root: str | Path,
    modules: tuple[ParsedPythonModule, ...],
) -> StaticProjectGraph:
    builder = _PythonGraphBuilder(Path(project_root).resolve(), modules)
    return builder.build()


@dataclass
class _CallableContext:
    symbol_id: str
    node: ast.FunctionDef | ast.AsyncFunctionDef
    file_path: str
    module_path: str
    current_class_name: str | None = None


@dataclass
class _ResolvedCall:
    callee_symbol_id: str
    callee_node: ast.FunctionDef | ast.AsyncFunctionDef
    call_node: ast.Call
    owner_statement: ast.stmt
    line_number: int
    column_offset: int


@dataclass
class _ModuleIndex:
    module_path: str
    file_path: str
    import_aliases: dict[str, str] = field(default_factory=dict)
    module_aliases: dict[str, str] = field(default_factory=dict)


class _PythonGraphBuilder:
    def __init__(self, project_root: Path, modules: tuple[ParsedPythonModule, ...]) -> None:
        self.project_root = project_root
        self.modules = modules
        self.symbols: list[StaticSymbol] = []
        self.signatures: list[StaticSignature] = []
        self.local_variables: list[StaticLocalVariable] = []
        self.edges: list[StaticFlowEdge] = []
        self.warnings: list[str] = []
        self.callables: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        self.contexts: list[_CallableContext] = []
        self.module_indexes: dict[str, _ModuleIndex] = {}
        self.top_level_symbols: dict[tuple[str, str], str] = {}
        self.class_symbols: dict[tuple[str, str], str] = {}
        self.method_symbols: dict[tuple[str, str, str], str] = {}

    def build(self) -> StaticProjectGraph:
        for module in self.modules:
            self._index_module(module.file_path, module.tree)

        for module in self.modules:
            self._index_imports(module.file_path, module.tree)

        for context in self.contexts:
            self.local_variables.extend(_collect_local_variables(context.symbol_id, context.node))
            self.edges.extend(self._link_calls(context))

        self.symbols.sort(key=lambda item: (item.file_path, item.start_line, item.qualified_name))
        self.signatures.sort(key=lambda item: item.symbol_id)
        self.local_variables.sort(key=lambda item: (item.symbol_id, item.line_number, item.name))
        self.edges.sort(key=lambda item: item.edge_id)
        return StaticProjectGraph(
            project_root=str(self.project_root),
            symbols=tuple(self.symbols),
            signatures=tuple(self.signatures),
            local_variables=tuple(self.local_variables),
            edges=tuple(self.edges),
            warnings=tuple(sorted(set(self.warnings))),
        )

    def _index_module(self, file_path: str, tree: ast.Module) -> None:
        module_path = _build_module_path(self.project_root, Path(file_path))
        self.module_indexes[file_path] = _ModuleIndex(module_path=module_path, file_path=file_path)

        for statement in tree.body:
            if _is_callable(statement):
                symbol_id = f"{module_path}.{statement.name}"
                self._add_callable_symbol(
                    symbol_id=symbol_id,
                    qualified_name=symbol_id,
                    display_name=statement.name,
                    file_path=file_path,
                    node=statement,
                    kind=StaticSymbolKind.FUNCTION,
                    module_path=module_path,
                    current_class_name=None,
                )
                self.top_level_symbols[(module_path, statement.name)] = symbol_id
                continue

            if isinstance(statement, ast.ClassDef):
                class_symbol_id = f"{module_path}.{statement.name}"
                self.class_symbols[(module_path, statement.name)] = class_symbol_id
                self.symbols.append(
                    StaticSymbol(
                        symbol_id=class_symbol_id,
                        language=LanguageId.PYTHON,
                        kind=StaticSymbolKind.CLASS,
                        qualified_name=class_symbol_id,
                        display_name=statement.name,
                        file_path=file_path,
                        start_line=statement.lineno,
                        end_line=getattr(statement, "end_lineno", statement.lineno),
                    )
                )
                for class_statement in statement.body:
                    if not _is_callable(class_statement):
                        continue
                    method_symbol_id = f"{class_symbol_id}.{class_statement.name}"
                    self._add_callable_symbol(
                        symbol_id=method_symbol_id,
                        qualified_name=method_symbol_id,
                        display_name=f"{statement.name}.{class_statement.name}",
                        file_path=file_path,
                        node=class_statement,
                        kind=StaticSymbolKind.METHOD,
                        module_path=module_path,
                        current_class_name=statement.name,
                        parent_symbol_id=class_symbol_id,
                        method_kind=_method_kind(class_statement),
                    )
                    self.method_symbols[
                        (module_path, statement.name, class_statement.name)
                    ] = method_symbol_id
                    self.edges.append(
                        StaticFlowEdge(
                            edge_id=f"contains:{class_symbol_id}:{method_symbol_id}",
                            kind=StaticFlowEdgeKind.CONTAINS,
                            source_symbol_id=class_symbol_id,
                            target_symbol_id=method_symbol_id,
                            detail=f"{statement.name} contains {class_statement.name}",
                            line_number=class_statement.lineno,
                        )
                    )

    def _add_callable_symbol(
        self,
        *,
        symbol_id: str,
        qualified_name: str,
        display_name: str,
        file_path: str,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        kind: StaticSymbolKind,
        module_path: str,
        current_class_name: str | None,
        parent_symbol_id: str | None = None,
        method_kind: MethodKind | None = None,
    ) -> None:
        self.symbols.append(
            StaticSymbol(
                symbol_id=symbol_id,
                language=LanguageId.PYTHON,
                kind=kind,
                qualified_name=qualified_name,
                display_name=display_name,
                file_path=file_path,
                start_line=node.lineno,
                end_line=getattr(node, "end_lineno", node.lineno),
                parent_symbol_id=parent_symbol_id,
                method_kind=method_kind,
            )
        )
        self.signatures.append(
            StaticSignature(
                symbol_id=symbol_id,
                parameters=_extract_parameters(node, kind, method_kind),
                return_type=_annotation_text(node.returns),
            )
        )
        self.callables[symbol_id] = node
        self.contexts.append(
            _CallableContext(
                symbol_id=symbol_id,
                node=node,
                file_path=file_path,
                module_path=module_path,
                current_class_name=current_class_name,
            )
        )

    def _index_imports(self, file_path: str, tree: ast.Module) -> None:
        module_index = self.module_indexes[file_path]
        for statement in tree.body:
            if isinstance(statement, ast.Import):
                for alias in statement.names:
                    alias_name = alias.asname or alias.name.split(".", maxsplit=1)[0]
                    module_index.module_aliases[alias_name] = alias.name
                continue

            if isinstance(statement, ast.ImportFrom):
                imported_module = _resolve_import_from_module(module_index.module_path, statement)
                if imported_module is None:
                    continue
                for alias in statement.names:
                    if alias.name == "*":
                        continue
                    local_name = alias.asname or alias.name
                    full_name = f"{imported_module}.{alias.name}" if imported_module else alias.name
                    module_index.import_aliases[local_name] = full_name
                    module_index.module_aliases[local_name] = full_name

    def _link_calls(self, context: _CallableContext) -> tuple[StaticFlowEdge, ...]:
        collector = _CallCollector()
        for child in context.node.body:
            collector.visit(child)

        edges: list[StaticFlowEdge] = []
        for call_node, owner_statement in collector.calls:
            resolved = self._resolve_call(context, call_node, owner_statement)
            if resolved is None:
                edges.append(self._build_unresolved_call_edge(context, call_node))
                continue
            edges.append(
                StaticFlowEdge(
                    edge_id=(
                        f"call:{context.symbol_id}:{resolved.callee_symbol_id}:"
                        f"{resolved.line_number}:{resolved.column_offset}"
                    ),
                    kind=StaticFlowEdgeKind.CALL,
                    source_symbol_id=context.symbol_id,
                    target_symbol_id=resolved.callee_symbol_id,
                    detail=_call_text(call_node),
                    line_number=resolved.line_number,
                )
            )
            edges.extend(_build_arg_edges(context.symbol_id, resolved))
            edges.extend(_build_return_edges(context.symbol_id, resolved))
        return tuple(edges)

    def _resolve_call(
        self,
        context: _CallableContext,
        call_node: ast.Call,
        owner_statement: ast.stmt,
    ) -> _ResolvedCall | None:
        callee_symbol_id = self._resolve_callee_symbol_id(context, call_node.func)
        if callee_symbol_id is None:
            return None
        callee_node = self.callables.get(callee_symbol_id)
        if callee_node is None:
            return None
        return _ResolvedCall(
            callee_symbol_id=callee_symbol_id,
            callee_node=callee_node,
            call_node=call_node,
            owner_statement=owner_statement,
            line_number=getattr(call_node, "lineno", getattr(owner_statement, "lineno", 0)),
            column_offset=getattr(call_node, "col_offset", 0),
        )

    def _resolve_callee_symbol_id(
        self,
        context: _CallableContext,
        function: ast.expr,
    ) -> str | None:
        module_index = self.module_indexes[context.file_path]

        if isinstance(function, ast.Name):
            same_module = self.top_level_symbols.get((context.module_path, function.id))
            if same_module is not None:
                return same_module
            imported_name = module_index.import_aliases.get(function.id)
            if imported_name is not None:
                return self._resolve_qualified_name(imported_name)
            return self._resolve_unique_display_name(function.id)

        if isinstance(function, ast.Attribute):
            owner_text = _expr_text(function.value)
            attribute_name = function.attr
            if owner_text in {"self", "cls"} and context.current_class_name is not None:
                return self.method_symbols.get(
                    (context.module_path, context.current_class_name, attribute_name)
                )

            class_method = self.method_symbols.get(
                (context.module_path, owner_text, attribute_name)
            )
            if class_method is not None:
                return class_method

            imported_owner = module_index.import_aliases.get(owner_text)
            if imported_owner is not None:
                resolved = self._resolve_qualified_name(f"{imported_owner}.{attribute_name}")
                if resolved is not None:
                    return resolved

            module_alias = module_index.module_aliases.get(owner_text)
            if module_alias is not None:
                resolved = self._resolve_qualified_name(f"{module_alias}.{attribute_name}")
                if resolved is not None:
                    return resolved

            return self._resolve_qualified_name(f"{owner_text}.{attribute_name}")

        return None

    def _resolve_qualified_name(self, qualified_name: str) -> str | None:
        module_name, _, member_name = qualified_name.rpartition(".")
        if module_name:
            top_level = self.top_level_symbols.get((module_name, member_name))
            if top_level is not None:
                return top_level
            class_symbol = self.class_symbols.get((module_name, member_name))
            if class_symbol is not None:
                return class_symbol

        class_module, _, class_name = module_name.rpartition(".")
        if class_module:
            method_symbol = self.method_symbols.get((class_module, class_name, member_name))
            if method_symbol is not None:
                return method_symbol

        for symbol in self.symbols:
            if symbol.qualified_name == qualified_name:
                return symbol.symbol_id
        return None

    def _resolve_unique_display_name(self, display_name: str) -> str | None:
        matches = [
            symbol.symbol_id
            for symbol in self.symbols
            if symbol.kind in {StaticSymbolKind.FUNCTION, StaticSymbolKind.METHOD}
            and symbol.display_name.rsplit(".", maxsplit=1)[-1] == display_name
        ]
        if len(matches) == 1:
            return matches[0]
        return None

    def _build_unresolved_call_edge(
        self,
        context: _CallableContext,
        call_node: ast.Call,
    ) -> StaticFlowEdge:
        line_number = getattr(call_node, "lineno", None)
        call_text = _call_text(call_node)
        return StaticFlowEdge(
            edge_id=f"unresolved:{context.symbol_id}:{line_number}:{call_text}",
            kind=StaticFlowEdgeKind.UNRESOLVED_CALL,
            source_symbol_id=context.symbol_id,
            target_symbol_id=None,
            target_slot=_callee_text(call_node.func),
            detail=call_text,
            line_number=line_number,
            resolution=StaticResolution.UNRESOLVED,
        )


class _CallCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.calls: list[tuple[ast.Call, ast.stmt]] = []
        self._statement_stack: list[ast.stmt] = []

    def visit(self, node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            return
        super().visit(node)

    def generic_visit(self, node: ast.AST) -> None:
        is_statement = isinstance(node, ast.stmt)
        if is_statement:
            self._statement_stack.append(node)
        try:
            if isinstance(node, ast.Call) and self._statement_stack:
                self.calls.append((node, self._statement_stack[-1]))
            super().generic_visit(node)
        finally:
            if is_statement:
                self._statement_stack.pop()


def _build_arg_edges(caller_symbol_id: str, resolved: _ResolvedCall) -> tuple[StaticFlowEdge, ...]:
    parameter_slots, vararg_slot, keyword_only_slots, kwarg_slot = _parameter_slots(
        resolved.callee_node,
        resolved.callee_symbol_id,
    )
    positional_index = 0
    edges: list[StaticFlowEdge] = []

    for arg_index, argument in enumerate(resolved.call_node.args):
        source_slot = _expr_text(argument)
        if positional_index < len(parameter_slots):
            target_slot = parameter_slots[positional_index]
            positional_index += 1
        elif vararg_slot is not None:
            target_slot = f"*{vararg_slot}"
        else:
            continue
        edges.append(
            StaticFlowEdge(
                edge_id=(
                    f"arg:{caller_symbol_id}:{resolved.callee_symbol_id}:"
                    f"{resolved.line_number}:{resolved.column_offset}:{arg_index}:{target_slot}"
                ),
                kind=StaticFlowEdgeKind.ARG,
                source_symbol_id=caller_symbol_id,
                target_symbol_id=resolved.callee_symbol_id,
                source_slot=source_slot,
                target_slot=target_slot,
                detail=f"{source_slot} -> {target_slot}",
                line_number=resolved.line_number,
            )
        )

    for keyword_index, keyword in enumerate(resolved.call_node.keywords):
        if keyword.arg is None:
            if kwarg_slot is None:
                continue
            target_slot = f"**{kwarg_slot}"
        elif keyword.arg in parameter_slots or keyword.arg in keyword_only_slots:
            target_slot = keyword.arg
        elif kwarg_slot is not None:
            target_slot = f"**{kwarg_slot}"
        else:
            continue
        source_slot = _expr_text(keyword.value)
        edges.append(
            StaticFlowEdge(
                edge_id=(
                    f"arg:{caller_symbol_id}:{resolved.callee_symbol_id}:"
                    f"{resolved.line_number}:{resolved.column_offset}:kw{keyword_index}:{target_slot}"
                ),
                kind=StaticFlowEdgeKind.ARG,
                source_symbol_id=caller_symbol_id,
                target_symbol_id=resolved.callee_symbol_id,
                source_slot=source_slot,
                target_slot=target_slot,
                detail=f"{source_slot} -> {target_slot}",
                line_number=resolved.line_number,
            )
        )
    return tuple(edges)


def _build_return_edges(
    caller_symbol_id: str,
    resolved: _ResolvedCall,
) -> tuple[StaticFlowEdge, ...]:
    target_slot: str | None = None
    statement = resolved.owner_statement
    if isinstance(statement, ast.Assign) and statement.value is resolved.call_node:
        if len(statement.targets) == 1:
            target_slot = _assignment_target_text(statement.targets[0])
    elif isinstance(statement, ast.AnnAssign) and statement.value is resolved.call_node:
        target_slot = _assignment_target_text(statement.target)
    elif isinstance(statement, ast.Return) and statement.value is resolved.call_node:
        target_slot = "return"
    elif isinstance(statement, ast.Expr) and statement.value is resolved.call_node:
        target_slot = "<discarded>"

    if target_slot is None:
        return ()

    return (
        StaticFlowEdge(
            edge_id=(
                f"return:{resolved.callee_symbol_id}:{caller_symbol_id}:"
                f"{resolved.line_number}:{resolved.column_offset}:{target_slot}"
            ),
            kind=StaticFlowEdgeKind.RETURN,
            source_symbol_id=resolved.callee_symbol_id,
            target_symbol_id=caller_symbol_id,
            source_slot="return",
            target_slot=target_slot,
            detail=f"{resolved.callee_node.name}.return -> {target_slot}",
            line_number=resolved.line_number,
        ),
    )


def _collect_local_variables(
    symbol_id: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[StaticLocalVariable, ...]:
    collector = _LocalVariableCollector(symbol_id)
    for child in node.body:
        collector.visit(child)
    return tuple(collector.variables)


class _LocalVariableCollector(ast.NodeVisitor):
    def __init__(self, symbol_id: str) -> None:
        self.symbol_id = symbol_id
        self.variables: list[StaticLocalVariable] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._add_target(target, node.lineno, _expr_text(node.value), None)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        value_preview = _expr_text(node.value) if node.value is not None else None
        self._add_target(node.target, node.lineno, value_preview, _annotation_text(node.annotation))
        self.generic_visit(node)

    def _add_target(
        self,
        target: ast.expr,
        line_number: int,
        value_preview: str | None,
        type_annotation: str | None,
    ) -> None:
        if isinstance(target, ast.Name):
            self.variables.append(
                StaticLocalVariable(
                    symbol_id=self.symbol_id,
                    name=target.id,
                    line_number=line_number,
                    value_preview=value_preview,
                    type_annotation=type_annotation,
                )
            )
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                self._add_target(element, line_number, value_preview, type_annotation)


def _extract_parameters(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    kind: StaticSymbolKind,
    method_kind: MethodKind | None,
) -> tuple[StaticParam, ...]:
    positional_args = [*node.args.posonlyargs, *node.args.args]
    if kind is StaticSymbolKind.METHOD and method_kind in {MethodKind.INSTANCE, MethodKind.CLASS}:
        if positional_args and positional_args[0].arg in {"self", "cls"}:
            positional_args = positional_args[1:]

    params = [
        StaticParam(
            name=arg.arg,
            type_annotation=_annotation_text(arg.annotation),
            default_value=None,
        )
        for arg in positional_args
    ]
    if node.args.vararg is not None:
        params.append(
            StaticParam(
                name=f"*{node.args.vararg.arg}",
                type_annotation=_annotation_text(node.args.vararg.annotation),
            )
        )
    for arg in node.args.kwonlyargs:
        params.append(
            StaticParam(
                name=arg.arg,
                type_annotation=_annotation_text(arg.annotation),
            )
        )
    if node.args.kwarg is not None:
        params.append(
            StaticParam(
                name=f"**{node.args.kwarg.arg}",
                type_annotation=_annotation_text(node.args.kwarg.annotation),
            )
        )
    return tuple(params)


def _parameter_slots(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    callee_symbol_id: str,
) -> tuple[list[str], str | None, set[str], str | None]:
    positional_parameters = [*node.args.posonlyargs, *node.args.args]
    if "." in callee_symbol_id and positional_parameters:
        receiver_name = positional_parameters[0].arg
        if receiver_name in {"self", "cls"}:
            positional_parameters = positional_parameters[1:]
    parameter_slots = [argument.arg for argument in positional_parameters]
    keyword_only_slots = {argument.arg for argument in node.args.kwonlyargs}
    vararg_slot = node.args.vararg.arg if node.args.vararg is not None else None
    kwarg_slot = node.args.kwarg.arg if node.args.kwarg is not None else None
    return parameter_slots, vararg_slot, keyword_only_slots, kwarg_slot


def _method_kind(node: ast.FunctionDef | ast.AsyncFunctionDef) -> MethodKind:
    for decorator in node.decorator_list:
        name = _decorator_name(decorator)
        if name == "staticmethod":
            return MethodKind.STATIC
        if name == "classmethod":
            return MethodKind.CLASS
    return MethodKind.INSTANCE


def _decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return _expr_text(node)


def _resolve_import_from_module(module_path: str, node: ast.ImportFrom) -> str | None:
    module = node.module or ""
    if node.level == 0:
        return module
    current_parts = module_path.split(".")[:-1]
    keep_count = max(0, len(current_parts) - node.level + 1)
    base_parts = current_parts[:keep_count]
    if module:
        base_parts.extend(module.split("."))
    return ".".join(base_parts)


def _build_module_path(project_root: Path, file_path: Path) -> str:
    relative = file_path.resolve().relative_to(project_root)
    parts = list(relative.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts:
        return file_path.stem
    return ".".join(parts)


def _annotation_text(annotation: ast.AST | None) -> str | None:
    if annotation is None:
        return UNKNOWN
    return _expr_text(annotation)


def _expr_text(node: ast.AST | None) -> str:
    if node is None:
        return ""
    return ast.unparse(node)


def _call_text(node: ast.Call) -> str:
    return _expr_text(node)


def _callee_text(node: ast.expr) -> str:
    return _expr_text(node)


def _assignment_target_text(node: ast.expr) -> str:
    return _expr_text(node)


def _is_callable(node: ast.AST) -> bool:
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
