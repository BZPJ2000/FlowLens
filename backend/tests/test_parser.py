import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.parser import CodeParser


def test_parse_project_uses_project_relative_paths(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    file_path = src_dir / "main.py"
    file_path.write_text("def run(data: dict) -> bool:\n    return bool(data)\n", encoding="utf-8")

    results = CodeParser().parse_project(str(tmp_path))

    assert len(results) == 1
    assert results[0].file_path == "src/main.py"
    assert (tmp_path / results[0].file_path).exists()


def test_python_ast_parser_extracts_aliases_functions_and_class_methods(tmp_path):
    file_path = tmp_path / "pipeline.py"
    file_path.write_text(
        "\n".join([
            "import numpy as np",
            "from utils.formatter import format_result as fmt",
            "",
            "def run(data: dict, limit: int = 3) -> bool:",
            "    return bool(data)",
            "",
            "class Processor:",
            "    def __init__(self, cfg: dict):",
            "        self.cfg = cfg",
            "",
            "    async def process(self, data: dict) -> str:",
            "        def nested():",
            "            return 'ignored'",
            "        return str(data)",
        ]),
        encoding="utf-8",
    )

    result = CodeParser().parse_file(str(file_path), root_dir=str(tmp_path))

    assert result is not None
    assert [(i.variable_name, i.source_module) for i in result.imports] == [
        ("np", "numpy"),
        ("fmt", "utils.formatter"),
    ]
    assert result.imports[1].alias == "format_result"
    assert [(f.name, f.return_type) for f in result.functions] == [("run", "bool")]
    assert result.functions[0].params == [
        {"name": "data", "type": "dict"},
        {"name": "limit", "type": "int"},
    ]
    assert [(e.variable_name, e.is_function, e.is_class) for e in result.exports] == [
        ("run", True, False),
        ("Processor", False, True),
    ]
    assert len(result.classes) == 1
    assert [m.name for m in result.classes[0].methods] == ["__init__", "process"]
    assert result.classes[0].methods[0].params == [{"name": "cfg", "type": "dict"}]
    assert result.classes[0].methods[1].params == [{"name": "data", "type": "dict"}]
    assert result.classes[0].methods[1].is_async is True


def test_python_ast_parser_extracts_internal_function_calls(tmp_path):
    file_path = tmp_path / "pipeline.py"
    file_path.write_text(
        "\n".join([
            "def load() -> dict:",
            "    return {'email': 'a@example.com'}",
            "",
            "def validate(email: str, subject: str) -> bool:",
            "    return bool(email and subject)",
            "",
            "def run(email: str, subject: str) -> bool:",
            "    return validate(email, subject)",
        ]),
        encoding="utf-8",
    )

    result = CodeParser().parse_file(str(file_path), root_dir=str(tmp_path))

    assert result is not None
    calls = [
        (call.caller_name, call.callee_name, [arg["name"] for arg in call.args])
        for call in result.calls
    ]
    assert ("run", "validate", ["email", "subject"]) in calls


def test_typescript_ast_parser_extracts_functions_classes_and_calls(tmp_path):
    file_path = tmp_path / "pipeline.ts"
    file_path.write_text(
        "\n".join([
            "import { format as fmt } from './formatter';",
            "export function validate(email: string, subject: string): boolean {",
            "  return Boolean(email && subject);",
            "}",
            "export const run = async (email: string, subject: string): Promise<boolean> => {",
            "  return validate(email, subject);",
            "};",
            "export class Processor {",
            "  process(data: Record<string, string>): string {",
            "    return fmt(data);",
            "  }",
            "}",
        ]),
        encoding="utf-8",
    )

    result = CodeParser().parse_file(str(file_path), root_dir=str(tmp_path))

    assert result is not None
    assert [(i.variable_name, i.source_module, i.alias) for i in result.imports] == [
        ("fmt", "./formatter", "format"),
    ]
    assert [(f.name, f.return_type, f.is_exported, f.is_async) for f in result.functions] == [
        ("validate", "boolean", True, False),
        ("run", "Promise", True, True),
    ]
    assert result.functions[0].params == [
        {"name": "email", "type": "string"},
        {"name": "subject", "type": "string"},
    ]
    assert len(result.classes) == 1
    assert result.classes[0].name == "Processor"
    assert result.classes[0].methods[0].name == "process"
    calls = [
        (call.caller_name, call.callee_name, [arg["name"] for arg in call.args])
        for call in result.calls
    ]
    assert ("run", "validate", ["email", "subject"]) in calls
    assert ("process", "fmt", ["data"]) in calls


def test_scan_project_filters_configs_tests_and_non_code_assets(tmp_path):
    files = {
        "src/main.ts": "export function run(data: string): boolean { return !!data }",
        "src/worker.py": "def process(data: dict) -> bool:\n    return bool(data)\n",
        "vite.preload.config.ts": "export default {}",
        "tailwind.config.js": "module.exports = {}",
        "tests/test_worker.py": "def test_worker():\n    assert True\n",
        "src/main.spec.ts": "test('x', () => {})",
        "README.md": "# docs",
        "package.json": "{}",
    }
    for rel_path, content in files.items():
        path = tmp_path / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    results, stats = CodeParser().scan_project(str(tmp_path))

    assert sorted(r.file_path for r in results) == ["src/main.ts", "src/worker.py"]
    assert stats.discovered_files == len(files)
    assert stats.unsupported_extension_files == 2
    assert stats.parsed_files == 2
    assert stats.ignored_files >= 4
