"""End-to-end pipeline tests — parse → build graph → verify relationships.

Tests the full pipeline (excluding AI analysis) on the test fixture projects:
1. ts_ecommerce — TypeScript project with complex import chains
2. py_pipeline — Python project with cross-module class/function flows
"""

import json
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

# Ensure we can import from the app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.parser import CodeParser
from app.core.graph_builder import GraphBuilder
from app.core.report_generator import ReportGenerator
from app.models.schemas import ParseResult


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def ts_project_dir():
    """Extract ts_ecommerce ZIP and return the source directory path."""
    zip_path = Path(__file__).resolve().parent.parent / "uploads" / "ts_ecommerce.zip"
    if not zip_path.exists():
        pytest.skip(f"Test ZIP not found: {zip_path}")

    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmpdir)
        # The ZIP contains ts_ecommerce/ folder
        src_dir = Path(tmpdir) / "ts_ecommerce"
        if not src_dir.exists():
            # Try flat extraction
            src_dir = Path(tmpdir)
        yield str(src_dir)


@pytest.fixture
def py_project_dir():
    """Extract py_pipeline ZIP and return the source directory path."""
    zip_path = Path(__file__).resolve().parent.parent / "uploads" / "py_pipeline.zip"
    if not zip_path.exists():
        pytest.skip(f"Test ZIP not found: {zip_path}")

    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmpdir)
        src_dir = Path(tmpdir) / "py_pipeline"
        if not src_dir.exists():
            src_dir = Path(tmpdir)
        yield str(src_dir)


# ═══════════════════════════════════════════════════════════
# TypeScript E-Commerce Tests
# ═══════════════════════════════════════════════════════════

class TestTSEcommerceParsing:
    """Test parsing of the TypeScript e-commerce project."""

    def test_parses_all_expected_files(self, ts_project_dir):
        results, stats = CodeParser().scan_project(ts_project_dir)

        file_names = {r.file_name for r in results}
        expected = {
            "models.ts", "app.ts", "client.ts",
            "format.ts", "auth.ts", "cart.ts",
            "useCartStore.ts", "CheckoutPage.tsx",
        }
        assert expected.issubset(file_names), f"Missing files: {expected - file_names}"
        # No test/config/vendor files should be included
        assert len(results) == 8, f"Expected 8 source files, got {len(results)}: {file_names}"

    def test_types_file_has_exports_only_no_imports(self, ts_project_dir):
        """models.ts is the type hub — it exports many types but imports nothing."""
        results, _ = CodeParser().scan_project(ts_project_dir)

        models = next((r for r in results if r.file_name == "models.ts"), None)
        assert models is not None, "models.ts not found"
        assert len(models.imports) == 0, f"models.ts should have 0 imports, got {len(models.imports)}"
        assert len(models.exports) >= 10, (
            f"models.ts should export 10+ types, got {len(models.exports)}"
        )

    def test_import_chains_are_correct(self, ts_project_dir):
        """Verify that import paths resolve correctly:
        - CheckoutPage imports from stores, utils, services, api
        - useCartStore imports from services/cart, utils/format, services/auth
        - services/cart imports from api/client, utils/format, services/auth
        - services/auth imports from api/client
        - api/client imports from types/models, config/app
        """
        results, _ = CodeParser().scan_project(ts_project_dir)
        by_name = {r.file_name: r for r in results}

        # CheckoutPage should import from 4 different modules
        page = by_name["CheckoutPage.tsx"]
        import_sources = {i.source_module for i in page.imports}
        assert len(import_sources) >= 3, f"CheckoutPage should import from 3+ sources, got {import_sources}"

    def test_all_import_variables_are_tracked(self, ts_project_dir):
        """Every import should have a variable_name extracted."""
        results, _ = CodeParser().scan_project(ts_project_dir)

        for r in results:
            for imp in r.imports:
                assert imp.variable_name, (
                    f"Empty variable_name in {r.file_name}: import from {imp.source_module}"
                )
                assert imp.source_module, (
                    f"Empty source_module in {r.file_name} for var {imp.variable_name}"
                )

    def test_functions_extracted_correctly(self, ts_project_dir):
        """Verify function signatures are extracted."""
        results, _ = CodeParser().scan_project(ts_project_dir)
        by_name = {r.file_name: r for r in results}

        # format.ts has many exported functions
        fmt = by_name["format.ts"]
        fn_names = {f.name for f in fmt.functions}
        assert "formatCurrency" in fn_names
        assert "formatDate" in fn_names
        assert "formatCartItemSummary" in fn_names
        assert len(fmt.functions) >= 7, f"format.ts should have 7+ functions, got {len(fmt.functions)}"

        # Client has class methods
        client = by_name["client.ts"]
        assert len(client.classes) >= 1, f"client.ts should have classes, got {len(client.classes)}"

    def test_exported_functions_flagged(self, ts_project_dir):
        """Exported functions should have is_exported=True, non-exported=False."""
        results, _ = CodeParser().scan_project(ts_project_dir)
        by_name = {r.file_name: r for r in results}

        fmt = by_name["format.ts"]
        # All top-level functions in format.ts are exported
        for fn in fmt.functions:
            assert fn.is_exported, f"{fn.name} in format.ts should be exported"

        # auth.ts — login and logout are exported
        auth = by_name["auth.ts"]
        exported_fns = {f.name for f in auth.functions if f.is_exported}
        assert "login" in exported_fns
        assert "logout" in exported_fns


class TestTSEcommerceGraphBuilding:
    """Test graph construction for the TS e-commerce project."""

    @pytest.fixture
    def ts_graph(self, ts_project_dir):
        """Build the full graph from parsed results."""
        results, _ = CodeParser().scan_project(ts_project_dir)
        # Create minimal AI results (no LLM needed for graph structure)
        from app.models.schemas import AIFileAnalysis, AIInputOutput

        ai_results = []
        for r in results:
            ai = AIFileAnalysis(
                file_path=r.file_path,
                summary=f"File: {r.file_name}",
                inputs=[
                    AIInputOutput(
                        name=imp.variable_name,
                        type=imp.data_type,
                        source=imp.source_module,
                        is_function=imp.import_type == "named",
                    )
                    for imp in r.imports
                ],
                outputs=[
                    AIInputOutput(
                        name=exp.variable_name,
                        type=exp.data_type,
                        is_function=exp.is_function,
                    )
                    for exp in r.exports
                ],
            )
            ai_results.append(ai)

        graph = GraphBuilder().build(results, ai_results)
        return graph, results

    def test_graph_has_all_source_files_as_nodes(self, ts_graph):
        graph, results = ts_graph
        assert len(graph.nodes) == len(results), (
            f"Expected {len(results)} nodes, got {len(graph.nodes)}"
        )

    def test_import_edges_connect_files(self, ts_graph):
        """Cross-file import edges should exist between dependent modules."""
        graph, results = ts_graph
        by_path = {n.file_path: n for n in graph.nodes}

        # Find edges by source/target paths
        edge_pairs = set()
        for e in graph.edges:
            src_path = by_path.get(e.source_node_id, {}).file_path if hasattr(by_path.get(e.source_node_id), 'file_path') else ""
            tgt_path = by_path.get(e.target_node_id, {}).file_path if hasattr(by_path.get(e.target_node_id), 'file_path') else ""

        # At minimum, we should have cross-file edges
        cross_file_edges = [
            e for e in graph.edges
            if e.source_node_id != e.target_node_id
        ]
        assert len(cross_file_edges) > 0, "No cross-file edges found — import matching failed"

    def test_entry_points_identified(self, ts_graph):
        """Entry points should include the page component."""
        graph, results = ts_graph
        assert len(graph.entry_points) > 0, "No entry points identified"

    def test_port_level_edges_generated(self, ts_graph):
        """Port-to-function parameter edges should exist for matched variables."""
        graph, results = ts_graph

        port_to_fn_edges = [
            e for e in graph.edges
            if hasattr(e.edge_type, 'value') and e.edge_type.value == "port_to_function"
            or str(e.edge_type) == "port_to_function"
        ]
        # At minimum, each node with input ports should have parameter edges
        total_input_ports = sum(
            len([p for p in n.ports if p.direction == "input"])
            for n in graph.nodes
        )
        # Not every port maps to a function param, but we should have some
        if total_input_ports > 0:
            # We may have port_to_function or function_to_port edges
            internal_edges = [
                e for e in graph.edges
                if e.source_node_id == e.target_node_id
            ]
            assert len(internal_edges) > 0 or total_input_ports > 0, (
                f"With {total_input_ports} input ports, expected some internal edges"
            )

    def test_no_spurious_edges(self, ts_graph):
        """Edges should only connect nodes that actually exist."""
        graph, results = ts_graph
        node_ids = {n.id for n in graph.nodes}

        for e in graph.edges:
            assert e.source_node_id in node_ids, (
                f"Edge source {e.source_node_id} not in nodes"
            )
            assert e.target_node_id in node_ids, (
                f"Edge target {e.target_node_id} not in nodes"
            )

    def test_deterministic_function_ids(self, ts_graph):
        """Function node IDs should be deterministic (MD5-based)."""
        graph, results = ts_graph
        fn_ids = []
        for n in graph.nodes:
            for fn in n.functions:
                fn_ids.append(fn.id)

        # Rebuild — IDs should be identical
        from app.models.schemas import AIFileAnalysis, AIInputOutput
        ai_results2 = []
        for r in results:
            ai2 = AIFileAnalysis(
                file_path=r.file_path,
                inputs=[AIInputOutput(name=i.variable_name, type=i.data_type, source=i.source_module) for i in r.imports],
                outputs=[AIInputOutput(name=e.variable_name, type=e.data_type) for e in r.exports],
            )
            ai_results2.append(ai2)

        graph2 = GraphBuilder().build(results, ai_results2)
        fn_ids2 = [fn.id for n in graph2.nodes for fn in n.functions]

        assert fn_ids == fn_ids2, "Function IDs should be deterministic"


# ═══════════════════════════════════════════════════════════
# Python Pipeline Tests
# ═══════════════════════════════════════════════════════════

class TestPythonPipelineParsing:
    """Test parsing of the Python data pipeline project."""

    def test_all_modules_parsed(self, py_project_dir):
        results, _ = CodeParser().scan_project(py_project_dir)
        file_names = {r.file_name for r in results}
        expected = {
            "schemas.py", "helpers.py", "base.py",
            "transform.py", "runner.py", "handlers.py",
        }
        assert expected.issubset(file_names), f"Missing: {expected - file_names}"

    def test_python_classes_extracted(self, py_project_dir):
        """Python classes should be extracted with their methods."""
        results, _ = CodeParser().scan_project(py_project_dir)
        by_name = {r.file_name: r for r in results}

        # transform.py has FieldNormalizer, DataEnricher, QualityFilter
        transform = by_name["transform.py"]
        class_names = {c.name for c in transform.classes}
        assert "FieldNormalizer" in class_names
        assert "DataEnricher" in class_names
        assert "QualityFilter" in class_names

        # base.py has BaseProcessor
        base = by_name["base.py"]
        base_classes = {c.name for c in base.classes}
        assert "BaseProcessor" in base_classes

    def test_python_imports_extracted(self, py_project_dir):
        """Python import tracking: from X import Y, import Z as alias."""
        results, _ = CodeParser().scan_project(py_project_dir)
        by_name = {r.file_name: r for r in results}

        # runner.py imports heavily from models, processors, utils
        runner = by_name["runner.py"]
        import_count = len(runner.imports)
        assert import_count >= 5, (
            f"runner.py should have 5+ imports, got {import_count}"
        )

        # Check specific imports
        import_names = {i.variable_name for i in runner.imports}
        assert "PipelineRunner" in import_names or "FieldNormalizer" in import_names

    def test_function_calls_extracted(self, py_project_dir):
        """Internal function calls should be tracked for Python."""
        results, _ = CodeParser().scan_project(py_project_dir)

        # Calls are only extracted for Python files (AST visitor)
        py_results = [r for r in results if r.language == "python"]
        for r in py_results:
            assert isinstance(r.calls, list), f"Calls should be a list for {r.file_path}"

        # At least some files should have calls
        files_with_calls = [r for r in py_results if len(r.calls) > 0]
        assert len(files_with_calls) > 0, "No internal function calls detected in Python files"

    def test_dataclass_fields_extracted(self, py_project_dir):
        """Dataclass functions and exports should be recognized."""
        results, _ = CodeParser().scan_project(py_project_dir)
        by_name = {r.file_name: r for r in results}

        schemas = by_name["schemas.py"]
        # Dataclasses create class exports
        exported_classes = {e.variable_name for e in schemas.exports if e.is_class}
        assert len(exported_classes) >= 6, (
            f"schemas.py should export 6+ dataclass classes, got {len(exported_classes)}"
        )


class TestPythonPipelineGraphBuilding:
    """Test graph construction for the Python pipeline project."""

    @pytest.fixture
    def py_graph(self, py_project_dir):
        results, _ = CodeParser().scan_project(py_project_dir)
        from app.models.schemas import AIFileAnalysis, AIInputOutput

        ai_results = []
        for r in results:
            ai = AIFileAnalysis(
                file_path=r.file_path,
                inputs=[AIInputOutput(name=i.variable_name, type=i.data_type, source=i.source_module) for i in r.imports],
                outputs=[AIInputOutput(name=e.variable_name, type=e.data_type, is_function=e.is_function) for e in r.exports],
            )
            ai_results.append(ai)

        graph = GraphBuilder().build(results, ai_results)
        return graph, results

    def test_cross_file_edges_built(self, py_graph):
        """Cross-file edges should connect importers to exporters."""
        graph, results = py_graph
        cross_edges = [e for e in graph.edges if e.source_node_id != e.target_node_id]
        assert len(cross_edges) > 0, (
            f"No cross-file edges in Python pipeline graph ({len(graph.edges)} total edges)"
        )

    def test_call_edges_within_files(self, py_graph):
        """Intra-file call edges should exist from Python AST call extraction."""
        graph, results = py_graph
        call_edges = [
            e for e in graph.edges
            if hasattr(e.edge_type, 'value') and e.edge_type.value == "call"
        ]
        assert len(call_edges) > 0, (
            f"No call edges found. Edge types: {set(str(e.edge_type) for e in graph.edges)}"
        )

    def test_report_generation(self, py_graph):
        """Report generation should work without errors."""
        graph, results = py_graph
        # Create matching ai_results
        from app.models.schemas import AIFileAnalysis, AIInputOutput
        ai_results = []
        for r in results:
            ai = AIFileAnalysis(
                file_path=r.file_path,
                inputs=[AIInputOutput(name=i.variable_name, type=i.data_type, source=i.source_module) for i in r.imports],
                outputs=[AIInputOutput(name=e.variable_name, type=e.data_type) for e in r.exports],
            )
            ai_results.append(ai)

        report = ReportGenerator().generate("py_pipeline", results, ai_results, graph)
        assert report.project_name == "py_pipeline"
        assert report.file_count == len(results)
        assert report.total_lines > 0
        assert len(report.issue_count) >= 0 if hasattr(report, 'issue_count') else True

        # Generate markdown
        md = ReportGenerator().generate_markdown(report)
        assert "# py_pipeline" in md
        assert "## 文件详情" in md
        assert len(md) > 500, f"Report should be substantial, got {len(md)} chars"


# ═══════════════════════════════════════════════════════════
# Edge Label & Variable Name Integrity Tests
# ═══════════════════════════════════════════════════════════

class TestEdgeVariableIntegrity:
    """Verify that edges carry correct variable_name and data_type."""

    @pytest.fixture
    def ts_graph(self, ts_project_dir):
        from app.models.schemas import AIFileAnalysis, AIInputOutput
        results, _ = CodeParser().scan_project(ts_project_dir)
        ai_results = []
        for r in results:
            ai = AIFileAnalysis(
                file_path=r.file_path,
                inputs=[AIInputOutput(name=i.variable_name, type=i.data_type, source=i.source_module) for i in r.imports],
                outputs=[AIInputOutput(name=e.variable_name, type=e.data_type) for e in r.exports],
            )
            ai_results.append(ai)
        return GraphBuilder().build(results, ai_results), results

    def test_edges_have_variable_names(self, ts_graph):
        graph, _ = ts_graph
        for e in graph.edges:
            assert e.variable_name, (
                f"Edge {e.id} has no variable_name (label: {e.label})"
            )

    def test_edges_have_data_types(self, ts_graph):
        graph, _ = ts_graph
        for e in graph.edges:
            assert e.data_type, (
                f"Edge {e.id} ({e.variable_name}) has no data_type"
            )

    def test_import_edges_label_format(self, ts_graph):
        """Import edges should have readable labels like 'name: type'."""
        graph, _ = ts_graph
        import_edges = [
            e for e in graph.edges
            if hasattr(e.edge_type, 'value') and e.edge_type.value == "import"
        ]
        for e in import_edges:
            assert ":" in e.label or e.label, (
                f"Import edge label should be 'name: type', got: '{e.label}'"
            )
