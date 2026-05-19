"""Tests for graph_builder — verifies per-parameter edge generation."""

import sys
from pathlib import Path

# Ensure backend app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.graph_builder import GraphBuilder, make_fn_id, module_matches_path
from app.models.schemas import (
    ParseResult,
    FunctionSignature,
    FunctionCall,
    ClassDefinition,
    ExportInfo,
    ImportInfo,
    AIFileAnalysis,
    AIInputOutput,
)


def _make_parse(file_path, file_name, functions=None, imports=None, exports=None, classes=None, calls=None):
    return ParseResult(
        file_path=file_path,
        file_name=file_name,
        language="python",
        functions=functions or [],
        imports=imports or [],
        exports=exports or [],
        classes=classes or [],
        calls=calls or [],
    )


def _make_ai(file_path, inputs=None, outputs=None):
    return AIFileAnalysis(
        file_path=file_path,
        summary="test",
        detail="test detail",
        inputs=inputs or [],
        outputs=outputs or [],
        internal_structures=[],
        architecture_role="util",
        dependencies_summary="",
    )


class TestPortToParamEdges:
    """Test that port_to_function edges are generated for each matching param."""

    def test_single_param_match(self):
        """If file imports 'data' and has function with param 'data', create edge."""
        builder = GraphBuilder()

        parse_a = _make_parse(
            "a.py", "a.py",
            functions=[FunctionSignature(
                name="format_result",
                params=[{"name": "data", "type": "dict"}],
                return_type="str",
                is_exported=True,
            )],
            exports=[ExportInfo(variable_name="format_result", is_function=True, data_type="function")],
        )
        ai_a = _make_ai(
            "a.py",
            inputs=[AIInputOutput(name="data", type="dict", source="b", is_function=False, description="")],
            outputs=[AIInputOutput(name="format_result", type="function", source="", is_function=True, description="")],
        )

        graph = builder.build([parse_a], [ai_a])

        # Should have port_to_function edge: port 'data' → function 'format_result' param 'data'
        ptf_edges = [e for e in graph.edges if e.edge_type == "port_to_function"]
        assert len(ptf_edges) >= 1, f"Expected port_to_function edges, got {len(ptf_edges)}"

        edge = ptf_edges[0]
        assert edge.variable_name == "data"
        assert edge.target_function_id == make_fn_id("a.py", "format_result")

    def test_multiple_params_multiple_edges(self):
        """Function with 2 params matching 2 input ports → 2 port_to_function edges."""
        builder = GraphBuilder()

        parse_a = _make_parse(
            "validator.py", "validator.py",
            functions=[FunctionSignature(
                name="validate_input",
                params=[{"name": "email", "type": "str"}, {"name": "subject", "type": "str"}],
                return_type="bool",
                is_exported=True,
            )],
            exports=[ExportInfo(variable_name="validate_input", is_function=True, data_type="function")],
        )
        ai_a = _make_ai(
            "validator.py",
            inputs=[
                AIInputOutput(name="email", type="str", source="form", is_function=False, description=""),
                AIInputOutput(name="subject", type="str", source="form", is_function=False, description=""),
            ],
            outputs=[AIInputOutput(name="validate_input", type="function", source="", is_function=True, description="")],
        )

        graph = builder.build([parse_a], [ai_a])

        ptf_edges = [e for e in graph.edges if e.edge_type == "port_to_function"]
        # Should have 2 edges: one for 'email', one for 'subject'
        param_names = {e.variable_name for e in ptf_edges}
        assert "email" in param_names, f"Missing 'email' edge. Got: {param_names}"
        assert "subject" in param_names, f"Missing 'subject' edge. Got: {param_names}"

    def test_duplicate_ports_do_not_duplicate_parameter_edges(self):
        builder = GraphBuilder()

        parse_a = _make_parse(
            "validator.py", "validator.py",
            functions=[FunctionSignature(
                name="validate_input",
                params=[{"name": "email", "type": "str"}],
                return_type="bool",
            )],
        )
        ai_a = _make_ai(
            "validator.py",
            inputs=[
                AIInputOutput(name="email", type="str", source="form", is_function=False, description=""),
                AIInputOutput(name="email", type="str", source="form", is_function=False, description="duplicate"),
            ],
        )

        graph = builder.build([parse_a], [ai_a])

        ptf_edges = [
            e for e in graph.edges
            if e.edge_type == "port_to_function" and e.variable_name == "email"
        ]
        assert len(ptf_edges) == 1

    def test_function_params_create_missing_input_ports_and_one_edge_per_param(self):
        builder = GraphBuilder()

        parse_a = _make_parse(
            "validator.py", "validator.py",
            functions=[FunctionSignature(
                name="validate_input",
                params=[
                    {"name": "email", "type": "str"},
                    {"name": "subject", "type": "str"},
                    {"name": "retry", "type": "int"},
                ],
                return_type="bool",
            )],
        )

        graph = builder.build([parse_a], [])
        node = graph.nodes[0]
        input_ports = {p.name: p for p in node.ports if p.direction == "input"}

        assert {"email", "subject", "retry"} <= set(input_ports)
        assert all(input_ports[name].port_type == "param" for name in ["email", "subject", "retry"])
        param_edges = [
            e for e in graph.edges
            if e.edge_type == "port_to_function" and e.target_function_id == make_fn_id("validator.py", "validate_input")
        ]
        assert {e.variable_name for e in param_edges} == {"email", "subject", "retry"}

    def test_class_method_params_create_internal_edges(self):
        builder = GraphBuilder()

        parse_a = _make_parse(
            "processor.py", "processor.py",
            classes=[ClassDefinition(
                name="Processor",
                methods=[FunctionSignature(
                    name="process",
                    params=[{"name": "data", "type": "dict"}, {"name": "strict", "type": "bool"}],
                    return_type="str",
                )],
            )],
        )

        graph = builder.build([parse_a], [])

        param_edges = [e for e in graph.edges if e.edge_type == "port_to_function"]
        assert {e.variable_name for e in param_edges} == {"data", "strict"}
        assert all(e.target_function_id.startswith("m_") for e in param_edges)

    def test_function_to_port_edge(self):
        """Exported function should have function_to_port edge to output port."""
        builder = GraphBuilder()

        parse_a = _make_parse(
            "utils.py", "utils.py",
            functions=[FunctionSignature(
                name="format_result",
                params=[{"name": "data", "type": "dict"}],
                return_type="str",
                is_exported=True,
            )],
            exports=[ExportInfo(variable_name="format_result", is_function=True, data_type="function")],
        )
        ai_a = _make_ai(
            "utils.py",
            inputs=[AIInputOutput(name="data", type="dict", source="", is_function=False, description="")],
            outputs=[AIInputOutput(name="format_result", type="function", source="", is_function=True, description="")],
        )

        graph = builder.build([parse_a], [ai_a])

        ftp_edges = [e for e in graph.edges if e.edge_type == "function_to_port"]
        assert len(ftp_edges) >= 1, f"Expected function_to_port edges, got {len(ftp_edges)}"
        edge = ftp_edges[0]
        assert edge.variable_name == "format_result"
        assert edge.source_function_id == make_fn_id("utils.py", "format_result")

    def test_cross_file_import_edge(self):
        """File B imports 'format_result' from file A → import edge created."""
        builder = GraphBuilder()

        parse_a = _make_parse(
            "utils.py", "utils.py",
            functions=[FunctionSignature(
                name="format_result",
                params=[{"name": "data", "type": "dict"}],
                return_type="str",
                is_exported=True,
            )],
            exports=[ExportInfo(variable_name="format_result", is_function=True, data_type="function")],
        )
        parse_b = _make_parse(
            "main.py", "main.py",
            functions=[FunctionSignature(
                name="run",
                params=[{"name": "format_result", "type": "function"}],
                return_type="None",
                is_exported=False,
            )],
            imports=[ImportInfo(variable_name="format_result", source_module="utils", data_type="function")],
        )

        ai_a = _make_ai(
            "utils.py",
            outputs=[AIInputOutput(name="format_result", type="function", source="", is_function=True, description="")],
        )
        ai_b = _make_ai(
            "main.py",
            inputs=[AIInputOutput(name="format_result", type="function", source="utils", is_function=True, description="")],
        )

        graph = builder.build([parse_a, parse_b], [ai_a, ai_b])

        import_edges = [e for e in graph.edges if e.edge_type == "import"]
        assert len(import_edges) >= 1, f"Expected import edges, got {len(import_edges)}"
        # The edge should carry variable_name = "format_result"
        assert any(e.variable_name == "format_result" for e in import_edges)
        assert not [
            e for e in graph.edges
            if e.edge_type == "call" and e.source_node_id != e.target_node_id
        ], "Cross-file function calls duplicate file port import edges"

    def test_dotted_python_module_matches_slash_file_path_with_alias(self):
        builder = GraphBuilder()

        parse_a = _make_parse(
            "src/utils/formatter.py", "formatter.py",
            functions=[FunctionSignature(
                name="format_result",
                params=[{"name": "data", "type": "dict"}],
                return_type="str",
                is_exported=True,
            )],
            exports=[ExportInfo(variable_name="format_result", is_function=True, data_type="function")],
        )
        parse_b = _make_parse(
            "src/main.py", "main.py",
            imports=[ImportInfo(
                variable_name="fmt",
                alias="format_result",
                source_module="utils.formatter",
                data_type="function",
            )],
        )

        graph = builder.build([parse_a, parse_b], [])

        import_edges = [e for e in graph.edges if e.edge_type == "import"]
        assert len(import_edges) == 1
        edge = import_edges[0]
        assert edge.variable_name == "fmt"
        assert edge.source_port_id == "port-output-format_result"
        assert edge.target_port_id == "port-input-fmt"

    def test_module_path_matching_handles_relative_and_dotted_imports(self):
        assert module_matches_path("utils.formatter", "src/main.py", "src/utils/formatter.py")
        assert module_matches_path("./utils/formatter", "src/main.ts", "src/utils/formatter.ts")
        assert module_matches_path("./utils", "src/main.ts", "src/utils/index.ts")

    def test_no_init_in_functions(self):
        """Verify that __init__ is still in graph (filtering is frontend-only)."""
        builder = GraphBuilder()

        parse_a = _make_parse(
            "cls.py", "cls.py",
            functions=[
                FunctionSignature(name="__init__", params=[{"name": "self", "type": ""}], return_type="None"),
                FunctionSignature(name="process", params=[{"name": "x", "type": "int"}], return_type="str", is_exported=True),
            ],
            exports=[ExportInfo(variable_name="process", is_function=True, data_type="function")],
        )
        ai_a = _make_ai("cls.py")

        graph = builder.build([parse_a], [ai_a])

        # Backend should still include __init__ — filtering is frontend's job
        fn_names = [fn.name for n in graph.nodes for fn in n.functions]
        assert "__init__" in fn_names
        assert "process" in fn_names

    def test_definition_order_does_not_create_fake_call_edges(self):
        builder = GraphBuilder()

        parse_a = _make_parse(
            "pipeline.py", "pipeline.py",
            functions=[
                FunctionSignature(name="load", params=[], return_type="dict"),
                FunctionSignature(name="validate", params=[{"name": "data", "type": "dict"}], return_type="bool"),
            ],
        )

        graph = builder.build([parse_a], [])

        assert not [
            e for e in graph.edges
            if e.edge_type == "call" and e.variable_name == "load→validate"
        ], "Definition order is not a data-flow edge"

    def test_internal_call_creates_one_edge_per_argument(self):
        builder = GraphBuilder()

        parse_a = _make_parse(
            "pipeline.py", "pipeline.py",
            functions=[
                FunctionSignature(
                    name="run",
                    params=[
                        {"name": "email", "type": "str"},
                        {"name": "subject", "type": "str"},
                    ],
                    return_type="bool",
                ),
                FunctionSignature(
                    name="validate",
                    params=[
                        {"name": "email", "type": "str"},
                        {"name": "subject", "type": "str"},
                    ],
                    return_type="bool",
                ),
            ],
            calls=[
                FunctionCall(
                    caller_name="run",
                    callee_name="validate",
                    args=[
                        {"name": "email", "type": "str", "position": 0},
                        {"name": "subject", "type": "str", "position": 1},
                    ],
                ),
            ],
        )

        graph = builder.build([parse_a], [])

        call_edges = [e for e in graph.edges if e.edge_type == "call"]
        assert {e.variable_name for e in call_edges} == {"email", "subject"}
        assert all(e.source_node_id == e.target_node_id for e in call_edges)
        assert all(e.source_function_id and e.target_function_id for e in call_edges)
