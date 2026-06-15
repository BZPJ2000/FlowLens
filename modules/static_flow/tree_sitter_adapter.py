from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from tree_sitter import Language, Node, Parser

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

try:  # pragma: no cover - import availability is environment-specific.
    import tree_sitter_typescript as ts_typescript
except ImportError:  # pragma: no cover
    ts_typescript = None


UNKNOWN = "Unknown"
_CALLABLE_NODE_TYPES = {
    "function_declaration",
    "arrow_function",
    "function_expression",
    "method_definition",
}


@dataclass(frozen=True, kw_only=True)
class ParsedTreeSitterModule:
    file_path: str
    source_bytes: bytes
    root_node: Node
    language: LanguageId


@dataclass
class _CallableContext:
    symbol_id: str
    node: Node
    file_path: str
    module_path: str
    name: str
    current_class_name: str | None = None


@dataclass
class _ModuleIndex:
    module_path: str
    file_path: str
    import_aliases: dict[str, str] = field(default_factory=dict)
    module_aliases: dict[str, str] = field(default_factory=dict)


@dataclass
class _CallSite:
    node: Node
    owner_statement: Node
    line_number: int
    column_offset: int


@dataclass
class _ResolvedCall:
    callee_symbol_id: str
    callee_node: Node
    call_site: _CallSite


def parse_tree_sitter_file(file_path: Path) -> ParsedTreeSitterModule:
    source_bytes = file_path.read_bytes()
    language_id = _language_id_for_suffix(file_path.suffix)
    parser = Parser(_tree_sitter_language_for_suffix(file_path.suffix))
    tree = parser.parse(source_bytes)
    if tree.root_node.has_error:
        # Tree-sitter can recover from errors; keep the tree but surface a warning upstream.
        pass
    return ParsedTreeSitterModule(
        file_path=str(file_path),
        source_bytes=source_bytes,
        root_node=tree.root_node,
        language=language_id,
    )


def build_tree_sitter_static_graph(
    project_root: str | Path,
    modules: tuple[ParsedTreeSitterModule, ...],
) -> StaticProjectGraph:
    return _TreeSitterGraphBuilder(Path(project_root).resolve(), modules).build()


def supports_tree_sitter_suffix(suffix: str) -> bool:
    return suffix.lower() in {".ts", ".tsx", ".js", ".jsx"} and ts_typescript is not None


class _TreeSitterGraphBuilder:
    def __init__(self, project_root: Path, modules: tuple[ParsedTreeSitterModule, ...]) -> None:
        self.project_root = project_root
        self.modules = modules
        self.symbols: list[StaticSymbol] = []
        self.signatures: list[StaticSignature] = []
        self.local_variables: list[StaticLocalVariable] = []
        self.edges: list[StaticFlowEdge] = []
        self.warnings: list[str] = []
        self.callables: dict[str, Node] = {}
        self.contexts: list[_CallableContext] = []
        self.module_indexes: dict[str, _ModuleIndex] = {}
        self.top_level_symbols: dict[tuple[str, str], str] = {}
        self.class_symbols: dict[tuple[str, str], str] = {}
        self.method_symbols: dict[tuple[str, str, str], str] = {}
        self.source_by_file: dict[str, bytes] = {module.file_path: module.source_bytes for module in modules}

    def build(self) -> StaticProjectGraph:
        for module in self.modules:
            self._index_module(module)
        for module in self.modules:
            self._index_imports(module)
        for context in self.contexts:
            self.local_variables.extend(self._collect_local_variables(context))
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

    def _index_module(self, module: ParsedTreeSitterModule) -> None:
        module_path = _build_module_path(self.project_root, Path(module.file_path))
        self.module_indexes[module.file_path] = _ModuleIndex(module_path=module_path, file_path=module.file_path)

        for statement in _named_children(module.root_node):
            declaration = _export_declaration(statement) if statement.type == "export_statement" else statement
            if declaration.type == "function_declaration":
                name_node = declaration.child_by_field_name("name")
                if name_node is None:
                    continue
                name = self._text(module.file_path, name_node)
                self._add_callable(
                    symbol_id=f"{module_path}.{name}",
                    qualified_name=f"{module_path}.{name}",
                    display_name=name,
                    file_path=module.file_path,
                    node=declaration,
                    kind=StaticSymbolKind.FUNCTION,
                    module_path=module_path,
                    current_class_name=None,
                    language=module.language,
                )
                self.top_level_symbols[(module_path, name)] = f"{module_path}.{name}"
                continue

            arrow = _variable_callable(declaration)
            if arrow is not None:
                name_node, callable_node = arrow
                name = self._text(module.file_path, name_node)
                self._add_callable(
                    symbol_id=f"{module_path}.{name}",
                    qualified_name=f"{module_path}.{name}",
                    display_name=name,
                    file_path=module.file_path,
                    node=callable_node,
                    kind=StaticSymbolKind.FUNCTION,
                    module_path=module_path,
                    current_class_name=None,
                    language=module.language,
                )
                self.top_level_symbols[(module_path, name)] = f"{module_path}.{name}"
                continue

            if declaration.type == "class_declaration":
                self._add_class(module, module_path, declaration)

    def _add_class(self, module: ParsedTreeSitterModule, module_path: str, class_node: Node) -> None:
        name_node = class_node.child_by_field_name("name")
        body = class_node.child_by_field_name("body")
        if name_node is None:
            return
        class_name = self._text(module.file_path, name_node)
        class_symbol_id = f"{module_path}.{class_name}"
        self.class_symbols[(module_path, class_name)] = class_symbol_id
        self.symbols.append(
            StaticSymbol(
                symbol_id=class_symbol_id,
                language=module.language,
                kind=StaticSymbolKind.CLASS,
                qualified_name=class_symbol_id,
                display_name=class_name,
                file_path=module.file_path,
                start_line=_line(class_node),
                end_line=_end_line(class_node),
            )
        )
        if body is None:
            return
        for child in _named_children(body):
            if child.type != "method_definition":
                continue
            method_name_node = child.child_by_field_name("name") or _first_named_of_type(
                child, {"property_identifier", "identifier"}
            )
            if method_name_node is None:
                continue
            method_name = self._text(module.file_path, method_name_node)
            method_symbol_id = f"{class_symbol_id}.{method_name}"
            self._add_callable(
                symbol_id=method_symbol_id,
                qualified_name=method_symbol_id,
                display_name=f"{class_name}.{method_name}",
                file_path=module.file_path,
                node=child,
                kind=StaticSymbolKind.METHOD,
                module_path=module_path,
                current_class_name=class_name,
                language=module.language,
                parent_symbol_id=class_symbol_id,
                method_kind=MethodKind.STATIC if _has_child_text(self, module.file_path, child, "static") else MethodKind.INSTANCE,
            )
            self.method_symbols[(module_path, class_name, method_name)] = method_symbol_id
            self.edges.append(
                StaticFlowEdge(
                    edge_id=f"contains:{class_symbol_id}:{method_symbol_id}",
                    kind=StaticFlowEdgeKind.CONTAINS,
                    source_symbol_id=class_symbol_id,
                    target_symbol_id=method_symbol_id,
                    detail=f"{class_name} contains {method_name}",
                    line_number=_line(child),
                )
            )

    def _add_callable(
        self,
        *,
        symbol_id: str,
        qualified_name: str,
        display_name: str,
        file_path: str,
        node: Node,
        kind: StaticSymbolKind,
        module_path: str,
        current_class_name: str | None,
        language: LanguageId,
        parent_symbol_id: str | None = None,
        method_kind: MethodKind | None = None,
    ) -> None:
        self.symbols.append(
            StaticSymbol(
                symbol_id=symbol_id,
                language=language,
                kind=kind,
                qualified_name=qualified_name,
                display_name=display_name,
                file_path=file_path,
                start_line=_line(node),
                end_line=_end_line(node),
                parent_symbol_id=parent_symbol_id,
                method_kind=method_kind,
            )
        )
        self.signatures.append(
            StaticSignature(
                symbol_id=symbol_id,
                parameters=tuple(
                    StaticParam(name=name, type_annotation=type_annotation)
                    for name, type_annotation in self._extract_parameters(file_path, node, kind, method_kind)
                ),
                return_type=self._return_type(file_path, node),
            )
        )
        self.callables[symbol_id] = node
        self.contexts.append(
            _CallableContext(
                symbol_id=symbol_id,
                node=node,
                file_path=file_path,
                module_path=module_path,
                name=display_name.rsplit(".", maxsplit=1)[-1],
                current_class_name=current_class_name,
            )
        )

    def _index_imports(self, module: ParsedTreeSitterModule) -> None:
        module_index = self.module_indexes[module.file_path]
        for statement in _walk(module.root_node):
            if statement.type != "import_statement":
                continue
            imported_module = self._import_module_name(module.file_path, statement)
            if imported_module is None:
                continue
            for alias_node in _walk(statement):
                if alias_node.type == "import_specifier":
                    identifiers = [
                        node for node in _named_children(alias_node)
                        if node.type in {"identifier", "property_identifier"}
                    ]
                    if not identifiers:
                        continue
                    imported_name = self._text(module.file_path, identifiers[0])
                    local_name = self._text(module.file_path, identifiers[-1])
                    module_index.import_aliases[local_name] = f"{imported_module}.{imported_name}"
                    continue
                if alias_node.type == "namespace_import":
                    name_node = _first_named_of_type(alias_node, {"identifier"})
                    if name_node is not None:
                        module_index.module_aliases[self._text(module.file_path, name_node)] = imported_module
            clause = _first_named_of_type(statement, {"import_clause"})
            if clause is not None:
                first_identifier = _first_named_of_type(clause, {"identifier"})
                if first_identifier is not None:
                    local_name = self._text(module.file_path, first_identifier)
                    module_index.import_aliases[local_name] = f"{imported_module}.default"
                    module_index.module_aliases[local_name] = imported_module

    def _link_calls(self, context: _CallableContext) -> tuple[StaticFlowEdge, ...]:
        body = _callable_body(context.node)
        if body is None:
            body = context.node
        edges: list[StaticFlowEdge] = []
        for call_site in _collect_call_sites(body):
            resolved = self._resolve_call(context, call_site)
            if resolved is None:
                edges.append(self._unresolved_call_edge(context, call_site))
                continue
            edges.append(
                StaticFlowEdge(
                    edge_id=(
                        f"call:{context.symbol_id}:{resolved.callee_symbol_id}:"
                        f"{call_site.line_number}:{call_site.column_offset}"
                    ),
                    kind=StaticFlowEdgeKind.CALL,
                    source_symbol_id=context.symbol_id,
                    target_symbol_id=resolved.callee_symbol_id,
                    detail=self._text(context.file_path, call_site.node),
                    line_number=call_site.line_number,
                )
            )
            edges.extend(self._arg_edges(context.symbol_id, resolved))
            edges.extend(self._return_edges(context.symbol_id, resolved))
        return tuple(edges)

    def _resolve_call(self, context: _CallableContext, call_site: _CallSite) -> _ResolvedCall | None:
        callee_name = self._callee_name(context.file_path, call_site.node)
        if callee_name is None:
            return None
        callee_symbol_id = self._resolve_callee_symbol_id(context, callee_name)
        if callee_symbol_id is None:
            return None
        callee_node = self.callables.get(callee_symbol_id)
        if callee_node is None:
            return None
        return _ResolvedCall(callee_symbol_id=callee_symbol_id, callee_node=callee_node, call_site=call_site)

    def _resolve_callee_symbol_id(self, context: _CallableContext, callee_name: str) -> str | None:
        module_index = self.module_indexes[context.file_path]
        if "." not in callee_name:
            same_module = self.top_level_symbols.get((context.module_path, callee_name))
            if same_module is not None:
                return same_module
            imported_name = module_index.import_aliases.get(callee_name)
            if imported_name is not None:
                return self._resolve_qualified_name(imported_name)
            if context.current_class_name is not None:
                method = self.method_symbols.get((context.module_path, context.current_class_name, callee_name))
                if method is not None:
                    return method
            return self._resolve_unique_display_name(callee_name)

        owner_name, _, member_name = callee_name.rpartition(".")
        if owner_name in {"this", "self"} and context.current_class_name is not None:
            method = self.method_symbols.get((context.module_path, context.current_class_name, member_name))
            if method is not None:
                return method
        class_method = self.method_symbols.get((context.module_path, owner_name, member_name))
        if class_method is not None:
            return class_method
        imported_owner = module_index.import_aliases.get(owner_name)
        if imported_owner is not None:
            resolved = self._resolve_qualified_name(f"{imported_owner}.{member_name}")
            if resolved is not None:
                return resolved
        module_alias = module_index.module_aliases.get(owner_name)
        if module_alias is not None:
            resolved = self._resolve_qualified_name(f"{module_alias}.{member_name}")
            if resolved is not None:
                return resolved
        return self._resolve_qualified_name(callee_name)

    def _resolve_qualified_name(self, qualified_name: str) -> str | None:
        if qualified_name.endswith(".default"):
            module_name = qualified_name.removesuffix(".default")
            candidates = [
                symbol.symbol_id
                for symbol in self.symbols
                if symbol.symbol_id.startswith(f"{module_name}.")
                and symbol.kind is StaticSymbolKind.FUNCTION
            ]
            if len(candidates) == 1:
                return candidates[0]
        module_name, _, member_name = qualified_name.rpartition(".")
        top_level = self.top_level_symbols.get((module_name, member_name))
        if top_level is not None:
            return top_level
        class_symbol = self.class_symbols.get((module_name, member_name))
        if class_symbol is not None:
            return class_symbol
        class_module, _, class_name = module_name.rpartition(".")
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
        return matches[0] if len(matches) == 1 else None

    def _arg_edges(self, caller_symbol_id: str, resolved: _ResolvedCall) -> tuple[StaticFlowEdge, ...]:
        params = [name for name, _ in self._extract_parameters(
            self._file_path_for_symbol(resolved.callee_symbol_id),
            resolved.callee_node,
            StaticSymbolKind.FUNCTION,
            None,
        )]
        args = self._call_arguments(self._file_path_for_symbol(caller_symbol_id), resolved.call_site.node)
        edges: list[StaticFlowEdge] = []
        for index, argument in enumerate(args):
            target_slot = params[index] if index < len(params) else f"arg{index + 1}"
            edges.append(
                StaticFlowEdge(
                    edge_id=(
                        f"arg:{caller_symbol_id}:{resolved.callee_symbol_id}:"
                        f"{resolved.call_site.line_number}:{resolved.call_site.column_offset}:{index}:{target_slot}"
                    ),
                    kind=StaticFlowEdgeKind.ARG,
                    source_symbol_id=caller_symbol_id,
                    target_symbol_id=resolved.callee_symbol_id,
                    source_slot=argument,
                    target_slot=target_slot,
                    detail=f"{argument} -> {target_slot}",
                    line_number=resolved.call_site.line_number,
                )
            )
        return tuple(edges)

    def _return_edges(self, caller_symbol_id: str, resolved: _ResolvedCall) -> tuple[StaticFlowEdge, ...]:
        target_slot = self._call_result_target(
            self._file_path_for_symbol(caller_symbol_id),
            resolved.call_site,
        )
        if target_slot is None:
            return ()
        return (
            StaticFlowEdge(
                edge_id=(
                    f"return:{resolved.callee_symbol_id}:{caller_symbol_id}:"
                    f"{resolved.call_site.line_number}:{resolved.call_site.column_offset}:{target_slot}"
                ),
                kind=StaticFlowEdgeKind.RETURN,
                source_symbol_id=resolved.callee_symbol_id,
                target_symbol_id=caller_symbol_id,
                source_slot="return",
                target_slot=target_slot,
                detail=f"{_symbol_leaf(resolved.callee_symbol_id)}.return -> {target_slot}",
                line_number=resolved.call_site.line_number,
            ),
        )

    def _unresolved_call_edge(self, context: _CallableContext, call_site: _CallSite) -> StaticFlowEdge:
        return StaticFlowEdge(
            edge_id=(
                f"unresolved:{context.symbol_id}:"
                f"{call_site.line_number}:{call_site.column_offset}:{self._text(context.file_path, call_site.node)}"
            ),
            kind=StaticFlowEdgeKind.UNRESOLVED_CALL,
            source_symbol_id=context.symbol_id,
            target_symbol_id=None,
            target_slot=self._callee_name(context.file_path, call_site.node),
            detail=self._text(context.file_path, call_site.node),
            line_number=call_site.line_number,
            resolution=StaticResolution.UNRESOLVED,
        )

    def _collect_local_variables(self, context: _CallableContext) -> tuple[StaticLocalVariable, ...]:
        body = _callable_body(context.node)
        if body is None:
            return ()
        variables: list[StaticLocalVariable] = []
        for node in _walk(body):
            if node.type != "variable_declarator":
                continue
            name_node = node.child_by_field_name("name") or _first_named_of_type(node, {"identifier"})
            value_node = node.child_by_field_name("value")
            if name_node is None:
                continue
            variables.append(
                StaticLocalVariable(
                    symbol_id=context.symbol_id,
                    name=self._text(context.file_path, name_node),
                    line_number=_line(node),
                    value_preview=self._text(context.file_path, value_node) if value_node is not None else None,
                    type_annotation=_type_annotation_text(self, context.file_path, name_node),
                )
            )
        return tuple(variables)

    def _extract_parameters(
        self,
        file_path: str,
        node: Node,
        kind: StaticSymbolKind,
        method_kind: MethodKind | None,
    ) -> list[tuple[str, str | None]]:
        params_node = node.child_by_field_name("parameters") or _first_named_of_type(node, {"formal_parameters"})
        if params_node is None:
            return []
        params: list[tuple[str, str | None]] = []
        for child in _named_children(params_node):
            if child.type not in {"required_parameter", "optional_parameter", "rest_pattern", "identifier"}:
                continue
            name_node = child.child_by_field_name("pattern") or child.child_by_field_name("name")
            if name_node is None and child.type == "identifier":
                name_node = child
            if name_node is None:
                name_node = _first_named_of_type(child, {"identifier", "property_identifier"})
            if name_node is None:
                continue
            params.append((self._text(file_path, name_node), _type_annotation_text(self, file_path, child)))
        if kind is StaticSymbolKind.METHOD and method_kind in {MethodKind.INSTANCE, MethodKind.CLASS}:
            params = [(name, typ) for name, typ in params if name not in {"this", "self"}]
        return params

    def _return_type(self, file_path: str, node: Node) -> str | None:
        annotation = node.child_by_field_name("return_type")
        if annotation is None:
            for child in _named_children(node):
                if child.type == "type_annotation":
                    annotation = child
                    break
        return _clean_type_annotation(self._text(file_path, annotation)) if annotation else UNKNOWN

    def _import_module_name(self, file_path: str, node: Node) -> str | None:
        module_text = None
        for child in _named_children(node):
            if child.type == "string":
                module_text = self._text(file_path, child).strip("'\"")
                break
        if not module_text:
            return None
        if module_text.startswith("."):
            current = Path(file_path).resolve().relative_to(self.project_root).parent
            target = (current / module_text).as_posix()
        else:
            target = module_text
        return _module_name_from_import(self.project_root, Path(file_path), target)

    def _callee_name(self, file_path: str, call_node: Node) -> str | None:
        function_node = call_node.child_by_field_name("function")
        if function_node is None:
            function_node = _first_named_child(call_node)
        if function_node is None:
            return None
        return self._expression_name(file_path, function_node)

    def _expression_name(self, file_path: str, node: Node) -> str:
        if node.type in {"identifier", "property_identifier"}:
            return self._text(file_path, node)
        if node.type == "member_expression":
            object_node = node.child_by_field_name("object")
            property_node = node.child_by_field_name("property")
            if object_node is not None and property_node is not None:
                return f"{self._expression_name(file_path, object_node)}.{self._expression_name(file_path, property_node)}"
        return self._text(file_path, node)

    def _call_arguments(self, file_path: str, call_node: Node) -> list[str]:
        args_node = call_node.child_by_field_name("arguments") or _first_named_of_type(call_node, {"arguments"})
        if args_node is None:
            return []
        args = []
        for child in _named_children(args_node):
            if child.type in {",", "comment"}:
                continue
            args.append(self._text(file_path, child))
        return args

    def _call_result_target(self, file_path: str, call_site: _CallSite) -> str | None:
        owner = call_site.owner_statement
        if owner.type == "variable_declarator":
            name = owner.child_by_field_name("name") or _first_named_of_type(owner, {"identifier"})
            return self._text(file_path, name) if name is not None else None
        if owner.type == "return_statement":
            return "return"
        if owner.type == "assignment_expression":
            left = owner.child_by_field_name("left") or _first_named_child(owner)
            return self._text(file_path, left) if left is not None else None
        if owner.type == "expression_statement":
            return "<discarded>"
        return None

    def _file_path_for_symbol(self, symbol_id: str) -> str:
        for symbol in self.symbols:
            if symbol.symbol_id == symbol_id:
                return symbol.file_path
        return next(iter(self.source_by_file))

    def _text(self, file_path: str, node: Node | None) -> str:
        if node is None:
            return ""
        return self.source_by_file[file_path][node.start_byte:node.end_byte].decode("utf-8", "replace")


def _tree_sitter_language_for_suffix(suffix: str) -> Language:
    if ts_typescript is None:
        raise ImportError("tree_sitter_typescript is not installed")
    raw = ts_typescript.language_tsx() if suffix.lower() in {".tsx", ".jsx"} else ts_typescript.language_typescript()
    return Language(raw)


def _language_id_for_suffix(suffix: str) -> LanguageId:
    return LanguageId.TYPESCRIPT if suffix.lower() in {".ts", ".tsx"} else LanguageId.JAVASCRIPT


def _export_declaration(node: Node) -> Node:
    declaration = node.child_by_field_name("declaration")
    if declaration is not None:
        return declaration
    for child in _named_children(node):
        if child.type in {"function_declaration", "class_declaration", "lexical_declaration"}:
            return child
    return node


def _variable_callable(node: Node) -> tuple[Node, Node] | None:
    if node.type != "lexical_declaration":
        return None
    declarator = _first_named_of_type(node, {"variable_declarator"})
    if declarator is None:
        return None
    name = declarator.child_by_field_name("name") or _first_named_of_type(declarator, {"identifier"})
    value = declarator.child_by_field_name("value")
    if name is None or value is None or value.type not in {"arrow_function", "function_expression"}:
        return None
    return name, value


def _callable_body(node: Node) -> Node | None:
    return node.child_by_field_name("body") or _first_named_of_type(node, {"statement_block"})


def _collect_call_sites(root: Node) -> list[_CallSite]:
    calls: list[_CallSite] = []

    def visit(node: Node, owner_statement: Node | None) -> None:
        if node is not root and node.type in _CALLABLE_NODE_TYPES:
            return
        next_owner = node if _is_statement_owner(node) else owner_statement
        if node.type == "call_expression":
            calls.append(
                _CallSite(
                    node=node,
                    owner_statement=next_owner or node,
                    line_number=_line(node),
                    column_offset=node.start_point.column,
                )
            )
        for child in _named_children(node):
            visit(child, next_owner)

    visit(root, None)
    return calls


def _is_statement_owner(node: Node) -> bool:
    return node.type in {
        "variable_declarator",
        "return_statement",
        "assignment_expression",
        "expression_statement",
    }


def _named_children(node: Node) -> list[Node]:
    return [child for child in node.children if child.is_named]


def _walk(node: Node):
    yield node
    for child in _named_children(node):
        yield from _walk(child)


def _first_named_child(node: Node) -> Node | None:
    children = _named_children(node)
    return children[0] if children else None


def _first_named_of_type(node: Node, types: set[str]) -> Node | None:
    for child in _named_children(node):
        if child.type in types:
            return child
        found = _first_named_of_type(child, types)
        if found is not None:
            return found
    return None


def _type_annotation_text(builder: _TreeSitterGraphBuilder, file_path: str, node: Node) -> str | None:
    annotation = node.child_by_field_name("type")
    if annotation is None:
        for child in _named_children(node):
            if child.type == "type_annotation":
                annotation = child
                break
    return _clean_type_annotation(builder._text(file_path, annotation)) if annotation else UNKNOWN


def _clean_type_annotation(value: str) -> str:
    return value.strip().removeprefix(":").strip() or UNKNOWN


def _line(node: Node) -> int:
    return node.start_point.row + 1


def _end_line(node: Node) -> int:
    return node.end_point.row + 1


def _has_child_text(builder: _TreeSitterGraphBuilder, file_path: str, node: Node, text: str) -> bool:
    return any(builder._text(file_path, child) == text for child in node.children)


def _build_module_path(project_root: Path, file_path: Path) -> str:
    relative = file_path.resolve().relative_to(project_root)
    parts = list(relative.with_suffix("").parts)
    if parts and parts[-1] == "index":
        parts = parts[:-1]
    return ".".join(parts) if parts else file_path.stem


def _module_name_from_import(project_root: Path, importer: Path, import_text: str) -> str:
    normalized = import_text.replace("\\", "/").strip("/")
    if normalized.startswith("."):
        relative_parent = importer.resolve().relative_to(project_root).parent
        normalized = (relative_parent / normalized).as_posix()
    if normalized.startswith("@/"):
        normalized = f"frontend/src/{normalized[2:]}"
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return ".".join(part for part in Path(normalized).with_suffix("").parts if part and part != "index")


def _symbol_leaf(symbol_id: str) -> str:
    return symbol_id.rsplit(".", maxsplit=1)[-1]
