"""Phase 1: 源码解析引擎 — 提取文件结构和函数签名"""

import ast
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.models.schemas import (
    ClassDefinition,
    ExportInfo,
    FunctionCall,
    FunctionSignature,
    ImportInfo,
    ParseResult,
)

# 语言映射：文件扩展名 → 语言标识
EXT_TO_LANG = {
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".py": "python",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".swift": "swift",
    ".kt": "kotlin",
    ".vue": "vue",
    ".svelte": "svelte",
    ".sh": "bash",
}

SOURCE_EXTENSIONS = set(EXT_TO_LANG)

# 应忽略的目录
IGNORED_DIRS = {
    "node_modules", ".git", ".svn", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", "target", "bin", "obj",
    "out", ".vite", ".turbo", ".cache", ".parcel-cache", ".svelte-kit",
    ".idea", ".vscode", ".vs", ".storybook", "coverage", ".pytest_cache",
    ".mypy_cache", ".tox", ".eggs", "*.egg-info",
    "test", "tests", "__tests__", "__mocks__", "spec", "e2e",
    "cypress", "playwright-report", "storybook-static", "vendor",
    "third_party", "generated", "__generated__", "fixtures", "__fixtures__",
    "snapshots", "__snapshots__",
}

# 应忽略的文件模式
IGNORED_PATTERNS = [
    r"\.min\.(js|css)$",
    r"\.lock$",
    r"\.map$",
    r"\.d\.ts$",  # TypeScript declaration files
    r"\.config\.(js|jsx|ts|tsx|mjs|cjs)$",
    r"^vite(\..*)?\.config\.(js|ts|mjs|cjs)$",
    r"^vitest(\..*)?\.config\.(js|ts|mjs|cjs)$",
    r"^webpack(\..*)?\.config\.(js|ts|mjs|cjs)$",
    r"^rollup(\..*)?\.config\.(js|ts|mjs|cjs)$",
    r"^tailwind\.config\.(js|ts|mjs|cjs)$",
    r"^postcss\.config\.(js|ts|mjs|cjs)$",
    r"^eslint\.config\.(js|ts|mjs|cjs)$",
    r"^prettier\.config\.(js|ts|mjs|cjs)$",
    r"^babel\.config\.(js|ts|mjs|cjs)$",
    r"^jest\.config\.(js|ts|mjs|cjs)$",
    r"^karma\.conf\.(js|ts)$",
    r"^setupTests\.(js|ts|jsx|tsx)$",
    r"^vite-env\.d\.ts$",
    r"^next-env\.d\.ts$",
    r"^env\.d\.ts$",
    r"^tsconfig.*\.json$",
    r"^package\.json$",
    r"package-lock\.json$",
    r"yarn\.lock$",
    r"pnpm-lock\.yaml$",
    r"\.gitignore$",
    r"\.eslintrc",
    r"\.prettierrc",
    r".*\.(test|spec)\.(js|jsx|ts|tsx|py)$",
    r".*\.(stories|story)\.(js|jsx|ts|tsx)$",
    r".*\.(mock|fixture)\.(js|jsx|ts|tsx|py)$",
    r".*\.(generated|gen)\.(js|jsx|ts|tsx|py|go|rs|java)$",
    r".*\.pb\.(go|py|js|ts)$",
]


@dataclass(frozen=True)
class SourceScanStats:
    discovered_files: int
    unsupported_extension_files: int
    supported_extension_files: int
    ignored_files: int
    parsed_files: int


class CodeParser:
    """用正则表达式提取 import/export/函数签名。
    MVP 阶段使用正则（零依赖，0 token 消耗），后续可升级为 tree-sitter。
    """

    SUPPORTED_LANGS = {
        "typescript", "javascript", "python", "go", "rust", "java",
        "c", "cpp", "csharp", "ruby", "swift", "kotlin", "vue", "svelte", "bash",
    }

    def scan_project(self, root_dir: str) -> tuple[list[ParseResult], SourceScanStats]:
        """扫描并解析业务源码文件，返回解析结果和过滤统计。"""
        results = []
        files, stats = self._walk_source_files(root_dir)
        for file_path in files:
            result = self.parse_file(file_path, root_dir=root_dir)
            if result and result.line_count > 0:
                results.append(result)
        return results, SourceScanStats(
            discovered_files=stats.discovered_files,
            unsupported_extension_files=stats.unsupported_extension_files,
            supported_extension_files=stats.supported_extension_files,
            ignored_files=stats.ignored_files,
            parsed_files=len(results),
        )

    def parse_project(self, root_dir: str) -> list[ParseResult]:
        """解析整个项目目录"""
        results, _ = self.scan_project(root_dir)
        return results

    def parse_file(self, file_path: str, root_dir: str | None = None) -> ParseResult | None:
        """解析单个文件"""
        path = Path(file_path).resolve()
        lang = EXT_TO_LANG.get(path.suffix.lower(), "unknown")
        if lang == "unknown":
            return None

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None

        content_hash = hashlib.sha256(content.encode()).hexdigest()

        ts_ast = self._parse_ts_ast(path, lang) if lang in ("typescript", "javascript") else None
        if ts_ast:
            imports = self._ts_ast_imports(ts_ast)
            exports = self._ts_ast_exports(ts_ast)
            functions = self._ts_ast_functions(ts_ast)
            classes = self._ts_ast_classes(ts_ast)
            calls = self._ts_ast_calls(ts_ast)
        else:
            imports = self._extract_imports(content, lang)
            exports = self._extract_exports(content, lang)
            functions = self._extract_functions(content, lang)
            classes = self._extract_classes(content, lang)
            calls = self._extract_calls(content, lang)
        lines = content.split("\n")
        if root_dir:
            try:
                stored_path = path.relative_to(Path(root_dir).resolve()).as_posix()
            except ValueError:
                stored_path = path.name
        else:
            stored_path = path.name

        return ParseResult(
            file_path=stored_path,
            file_name=path.name,
            language=lang,
            content_hash=content_hash,
            imports=imports,
            exports=exports,
            functions=functions,
            classes=classes,
            calls=calls,
            line_count=len(lines),
            byte_size=len(content.encode("utf-8")),
        )

    def _walk_source_files(self, root_dir: str) -> tuple[list[str], SourceScanStats]:
        """遍历源码文件，过滤无关目录和文件"""
        files = []
        root = Path(root_dir)
        discovered = 0
        unsupported_ext = 0
        supported_ext = 0
        ignored = 0
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            discovered += 1
            if p.suffix.lower() not in SOURCE_EXTENSIONS:
                unsupported_ext += 1
                continue
            supported_ext += 1
            if self._should_ignore(p):
                ignored += 1
                continue
            files.append(str(p))
        return files, SourceScanStats(
            discovered_files=discovered,
            unsupported_extension_files=unsupported_ext,
            supported_extension_files=supported_ext,
            ignored_files=ignored,
            parsed_files=0,
        )

    def _should_ignore(self, path: Path) -> bool:
        parts = {part.lower() for part in path.parts}
        if parts & IGNORED_DIRS:
            return True
        if any(part.endswith(".egg-info") for part in parts):
            return True
        for pattern in IGNORED_PATTERNS:
            if re.search(pattern, path.name, re.IGNORECASE):
                return True
        return False

    def _parse_ts_ast(self, path: Path, lang: str) -> dict | None:
        script = Path(__file__).with_name("ts_ast_parser.mjs")
        if not script.exists():
            return None
        try:
            result = subprocess.run(
                ["node", str(script), str(path), lang],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(Path(__file__).resolve().parents[3]),
            )
            if result.returncode != 0 or not result.stdout.strip():
                return None
            return json.loads(result.stdout)
        except Exception:
            return None

    def _ts_ast_imports(self, data: dict) -> list[ImportInfo]:
        return [
            ImportInfo(
                variable_name=item.get("variable_name", ""),
                source_module=item.get("source_module", ""),
                import_type=item.get("import_type", "named"),
                alias=item.get("alias", ""),
                data_type=item.get("data_type", "unknown"),
            )
            for item in data.get("imports", [])
            if item.get("variable_name")
        ]

    def _ts_ast_exports(self, data: dict) -> list[ExportInfo]:
        return [
            ExportInfo(
                variable_name=item.get("variable_name", ""),
                export_type=item.get("export_type", "named"),
                data_type=item.get("data_type", "unknown"),
                is_function=bool(item.get("is_function", False)),
                is_class=bool(item.get("is_class", False)),
                is_type_only=bool(item.get("is_type_only", False)),
            )
            for item in data.get("exports", [])
            if item.get("variable_name")
        ]

    def _ts_ast_functions(self, data: dict) -> list[FunctionSignature]:
        return [
            FunctionSignature(
                name=item.get("name", ""),
                params=item.get("params", []),
                return_type=item.get("return_type", "unknown"),
                is_exported=bool(item.get("is_exported", False)),
                is_async=bool(item.get("is_async", False)),
                line_start=int(item.get("line_start", 0) or 0),
                line_end=int(item.get("line_end", 0) or 0),
            )
            for item in data.get("functions", [])
            if item.get("name")
        ]

    def _ts_ast_classes(self, data: dict) -> list[ClassDefinition]:
        classes = []
        for item in data.get("classes", []):
            methods = [
                FunctionSignature(
                    name=method.get("name", ""),
                    params=method.get("params", []),
                    return_type=method.get("return_type", "unknown"),
                    is_exported=bool(method.get("is_exported", False)),
                    is_async=bool(method.get("is_async", False)),
                    line_start=int(method.get("line_start", 0) or 0),
                    line_end=int(method.get("line_end", 0) or 0),
                )
                for method in item.get("methods", [])
                if method.get("name")
            ]
            if item.get("name"):
                classes.append(ClassDefinition(
                    name=item.get("name", ""),
                    methods=methods,
                    is_exported=bool(item.get("is_exported", False)),
                    line_start=int(item.get("line_start", 0) or 0),
                    line_end=int(item.get("line_end", 0) or 0),
                ))
        return classes

    def _ts_ast_calls(self, data: dict) -> list[FunctionCall]:
        return [
            FunctionCall(
                caller_name=item.get("caller_name", ""),
                callee_name=item.get("callee_name", ""),
                args=item.get("args", []),
                line=int(item.get("line", 0) or 0),
            )
            for item in data.get("calls", [])
            if item.get("caller_name") and item.get("callee_name")
        ]

    # ── Import 提取 ────────────────────────────

    def _extract_imports(self, content: str, lang: str) -> list[ImportInfo]:
        if lang in ("typescript", "javascript"):
            return self._extract_ts_imports(content)
        elif lang == "python":
            return self._extract_py_imports(content)
        elif lang == "go":
            return self._extract_go_imports(content)
        elif lang in ("java", "kotlin"):
            return self._extract_java_imports(content)
        elif lang in ("c", "cpp"):
            return self._extract_c_imports(content)
        elif lang == "csharp":
            return self._extract_cs_imports(content)
        elif lang == "rust":
            return self._extract_rust_imports(content)
        elif lang == "ruby":
            return self._extract_ruby_imports(content)
        elif lang == "swift":
            return self._extract_swift_imports(content)
        elif lang in ("vue", "svelte"):
            script = self._extract_vue_svelte_script(content)
            return self._extract_ts_imports(script) if script else []
        elif lang == "bash":
            return self._extract_bash_imports(content)
        return []

    def _extract_ts_imports(self, content: str) -> list[ImportInfo]:
        imports = []
        # import { a, b } from "x"
        p1 = re.finditer(
            r'import\s+\{([^}]+)\}\s+from\s+["\']([^"\']+)["\']', content
        )
        for m in p1:
            names = [n.strip() for n in m.group(1).split(",")]
            for raw_name in names:
                if raw_name:
                    raw_name = re.sub(r"^(type|typeof)\s+", "", raw_name).strip()
                    parts = re.split(r"\s+as\s+", raw_name)
                    original = parts[0].strip()
                    name = parts[-1].strip()
                    imports.append(ImportInfo(
                        variable_name=name,
                        source_module=m.group(2),
                        import_type="named",
                        alias=original if original != name else "",
                    ))

        # import X from "y"
        p2 = re.finditer(
            r'import\s+(\w+)\s+from\s+["\']([^"\']+)["\']', content
        )
        for m in p2:
            if m.group(1) not in {"type", "typeof"}:
                imports.append(ImportInfo(
                    variable_name=m.group(1),
                    source_module=m.group(2),
                    import_type="default",
                ))

        # import * as X from "y"
        p3 = re.finditer(
            r'import\s+\*\s+as\s+(\w+)\s+from\s+["\']([^"\']+)["\']', content
        )
        for m in p3:
            imports.append(ImportInfo(
                variable_name=m.group(1),
                source_module=m.group(2),
                import_type="namespace",
            ))

        # const { x } = require("y")
        p4 = re.finditer(
            r'(?:const|let|var)\s+\{([^}]+)\}\s*=\s*require\s*\(\s*["\']([^"\']+)["\']', content
        )
        for m in p4:
            names = [n.strip() for n in m.group(1).split(",")]
            for raw_name in names:
                if raw_name:
                    parts = raw_name.split(":", 1)
                    original = parts[0].strip()
                    name = parts[-1].strip()
                    imports.append(ImportInfo(
                        variable_name=name,
                        source_module=m.group(2),
                        import_type="destructured",
                        alias=original if original != name else "",
                    ))

        # Dynamic import: import("x")
        p5 = re.finditer(r'import\s*\(\s*["\']([^"\']+)["\']\s*\)', content)
        for m in p5:
            imports.append(ImportInfo(
                variable_name="(dynamic)",
                source_module=m.group(1),
                import_type="named",
            ))

        return imports

    def _extract_py_imports(self, content: str) -> list[ImportInfo]:
        imports = []
        tree = self._parse_py_ast(content)
        if tree is None:
            return imports

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    bound_name = alias.asname or alias.name.split(".")[0]
                    imports.append(ImportInfo(
                        variable_name=bound_name,
                        source_module=alias.name,
                        import_type="named",
                    ))
            elif isinstance(node, ast.ImportFrom):
                module = "." * node.level + (node.module or "")
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    imports.append(ImportInfo(
                        variable_name=alias.asname or alias.name,
                        source_module=module,
                        import_type="named",
                        alias=alias.name if alias.asname else "",
                    ))
        return imports

    # ── Export 提取 ────────────────────────────

    def _extract_exports(self, content: str, lang: str) -> list[ExportInfo]:
        if lang in ("typescript", "javascript"):
            return self._extract_ts_exports(content)
        elif lang == "python":
            return self._extract_py_exports(content)
        elif lang == "go":
            return self._extract_go_exports(content)
        elif lang in ("java", "kotlin"):
            return self._extract_java_exports(content)
        elif lang in ("c", "cpp"):
            return self._extract_c_exports(content)
        elif lang == "csharp":
            return self._extract_cs_exports(content)
        elif lang == "rust":
            return self._extract_rust_exports(content)
        elif lang == "ruby":
            return self._extract_ruby_exports(content)
        elif lang == "swift":
            return self._extract_swift_exports(content)
        elif lang in ("vue", "svelte"):
            script = self._extract_vue_svelte_script(content)
            return self._extract_ts_exports(script) if script else []
        elif lang == "bash":
            return self._extract_bash_exports(content)
        return []

    def _extract_ts_exports(self, content: str) -> list[ExportInfo]:
        exports = []
        # export const foo = ..., export function foo, export class Foo
        for m in re.finditer(
            r'export\s+(?:const|let|var|function|class|interface|type|enum)\s+(\w+)',
            content,
        ):
            is_func = "function" in m.group(0)
            is_class = "class" in m.group(0)
            exports.append(ExportInfo(
                variable_name=m.group(1),
                export_type="named",
                is_function=is_func,
                is_class=is_class,
            ))
        # export default function/class/expr
        for m in re.finditer(r'export\s+default\s+(?:function|class)?\s*(\w*)', content):
            exports.append(ExportInfo(
                variable_name=m.group(1) or "default",
                export_type="default",
            ))
        return exports

    def _extract_py_exports(self, content: str) -> list[ExportInfo]:
        exports = []
        tree = self._parse_py_ast(content)
        if tree is None:
            return exports

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                exports.append(ExportInfo(
                    variable_name=node.name,
                    is_function=True,
                ))
            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                exports.append(ExportInfo(
                    variable_name=node.name,
                    is_class=True,
                ))
        return exports

    # ── 函数提取 ──────────────────────────────

    def _extract_functions(self, content: str, lang: str) -> list[FunctionSignature]:
        if lang in ("typescript", "javascript"):
            return self._extract_ts_functions(content)
        elif lang == "python":
            return self._extract_py_functions(content)
        elif lang == "go":
            return self._extract_go_functions(content)
        elif lang in ("java", "kotlin"):
            return self._extract_java_functions(content)
        elif lang in ("c", "cpp"):
            return self._extract_c_functions(content)
        elif lang == "csharp":
            return self._extract_cs_functions(content)
        elif lang == "rust":
            return self._extract_rust_functions(content)
        elif lang == "ruby":
            return self._extract_ruby_functions(content)
        elif lang == "swift":
            return self._extract_swift_functions(content)
        elif lang in ("vue", "svelte"):
            script = self._extract_vue_svelte_script(content)
            return self._extract_ts_functions(script) if script else []
        elif lang == "bash":
            return self._extract_bash_functions(content)
        return []

    def _extract_ts_functions(self, content: str) -> list[FunctionSignature]:
        funcs = []
        # function name(params) { ... }
        for m in re.finditer(
            r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)\s*(?::\s*(\S+))?',
            content,
        ):
            params = self._parse_ts_params(m.group(2))
            funcs.append(FunctionSignature(
                name=m.group(1),
                params=params,
                return_type=m.group(3) or "unknown",
                is_exported="export" in content[max(0, m.start() - 30):m.start()],
                is_async="async" in content[max(0, m.start() - 30):m.start()],
            ))
        # const/let name = (params): Type => { ... }
        for m in re.finditer(
            r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*(?::\s*(\S+))?\s*=>',
            content,
        ):
            params = self._parse_ts_params(m.group(2))
            funcs.append(FunctionSignature(
                name=m.group(1),
                params=params,
                return_type=m.group(3) or "unknown",
                is_exported="export" in content[max(0, m.start() - 30):m.start()],
                is_async="async" in content[max(0, m.start() - 30):m.start()],
            ))
        # async name(params): Type { }
        for m in re.finditer(
            r'(?:export\s+)?async\s+(\w+)\s*\(([^)]*)\)\s*(?::\s*(\S+))?\s*\{',
            content,
        ):
            if m.group(1) != "function":
                params = self._parse_ts_params(m.group(2))
                funcs.append(FunctionSignature(
                    name=m.group(1),
                    params=params,
                    return_type=m.group(3) or "unknown",
                    is_exported="export" in content[max(0, m.start() - 30):m.start()],
                    is_async=True,
                ))
        return funcs

    def _extract_py_functions(self, content: str) -> list[FunctionSignature]:
        """Extract top-level functions only (not class methods)."""
        funcs = []
        tree = self._parse_py_ast(content)
        if tree is None:
            return funcs

        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            params = self._parse_py_ast_params(node.args)
            funcs.append(FunctionSignature(
                name=node.name,
                params=params,
                return_type=self._annotation_to_str(node.returns),
                is_exported=not node.name.startswith("_"),
                is_async=isinstance(node, ast.AsyncFunctionDef),
                line_start=getattr(node, "lineno", 0),
                line_end=getattr(node, "end_lineno", 0) or 0,
            ))
        return funcs

    # ── 类提取 ────────────────────────────────

    def _extract_classes(self, content: str, lang: str) -> list[ClassDefinition]:
        if lang in ("typescript", "javascript"):
            return self._extract_ts_classes(content)
        elif lang == "python":
            return self._extract_py_classes(content)
        elif lang == "go":
            return self._extract_go_classes(content)
        elif lang in ("java", "kotlin"):
            return self._extract_java_classes(content)
        elif lang in ("c", "cpp"):
            return self._extract_c_classes(content)
        elif lang == "csharp":
            return self._extract_cs_classes(content)
        elif lang == "rust":
            return self._extract_rust_classes(content)
        elif lang == "ruby":
            return self._extract_ruby_classes(content)
        elif lang == "swift":
            return self._extract_swift_classes(content)
        elif lang in ("vue", "svelte"):
            script = self._extract_vue_svelte_script(content)
            return self._extract_ts_classes(script) if script else []
        return []

    def _extract_ts_classes(self, content: str) -> list[ClassDefinition]:
        classes = []
        for m in re.finditer(
            r'(?:export\s+)?class\s+(\w+)',
            content,
        ):
            classes.append(ClassDefinition(
                name=m.group(1),
                is_exported="export" in content[max(0, m.start() - 30):m.start()],
            ))
        return classes

    def _extract_py_classes(self, content: str) -> list[ClassDefinition]:
        """Extract top-level class definitions with their direct methods."""
        classes = []
        tree = self._parse_py_ast(content)
        if tree is None:
            return classes

        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            class_def = ClassDefinition(
                name=node.name,
                is_exported=not node.name.startswith("_"),
                line_start=getattr(node, "lineno", 0),
                line_end=getattr(node, "end_lineno", 0) or 0,
            )
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                class_def.methods.append(FunctionSignature(
                    name=item.name,
                    params=self._parse_py_ast_params(item.args, skip_self=True),
                    return_type=self._annotation_to_str(item.returns),
                    is_exported=not item.name.startswith("_"),
                    is_async=isinstance(item, ast.AsyncFunctionDef),
                    line_start=getattr(item, "lineno", 0),
                    line_end=getattr(item, "end_lineno", 0) or 0,
                ))
            classes.append(class_def)

        return classes

    # ── 调用流提取 ─────────────────────────────

    def _extract_calls(self, content: str, lang: str) -> list[FunctionCall]:
        if lang == "python":
            return self._extract_py_calls(content)
        elif lang in ("typescript", "javascript"):
            return self._extract_ts_calls(content)
        elif lang == "go":
            return self._extract_go_calls(content)
        elif lang in ("java", "kotlin"):
            return self._extract_java_calls(content)
        elif lang == "csharp":
            return self._extract_cs_calls(content)
        elif lang == "rust":
            return self._extract_rust_calls(content)
        elif lang in ("c", "cpp"):
            return self._extract_c_calls(content)
        elif lang == "ruby":
            return self._extract_ruby_calls(content)
        elif lang == "swift":
            return self._extract_swift_calls(content)
        elif lang in ("vue", "svelte"):
            script = self._extract_vue_svelte_script(content)
            return self._extract_ts_calls(script) if script else []
        return []

    def _extract_py_calls(self, content: str) -> list[FunctionCall]:
        tree = self._parse_py_ast(content)
        if tree is None:
            return []

        calls: list[FunctionCall] = []
        function_stack: list[str] = []

        class CallVisitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node: ast.FunctionDef):
                function_stack.append(node.name)
                self.generic_visit(node)
                function_stack.pop()

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                function_stack.append(node.name)
                self.generic_visit(node)
                function_stack.pop()

            def visit_Call(self, node: ast.Call):
                if function_stack:
                    callee = self._callee_name(node.func)
                    if callee:
                        calls.append(FunctionCall(
                            caller_name=function_stack[-1],
                            callee_name=callee,
                            args=[
                                {
                                    "name": self._arg_name(arg),
                                    "type": "unknown",
                                    "position": idx,
                                }
                                for idx, arg in enumerate(node.args)
                                if self._arg_name(arg)
                            ],
                            line=getattr(node, "lineno", 0),
                        ))
                self.generic_visit(node)

            def _callee_name(self, node: ast.AST) -> str:
                if isinstance(node, ast.Name):
                    return node.id
                if isinstance(node, ast.Attribute):
                    return node.attr
                return ""

            def _arg_name(self, node: ast.AST) -> str:
                if isinstance(node, ast.Name):
                    return node.id
                if isinstance(node, ast.Attribute):
                    return node.attr
                if isinstance(node, ast.Constant):
                    return repr(node.value)
                try:
                    return ast.unparse(node).strip()
                except Exception:
                    return ""

        CallVisitor().visit(tree)
        return calls

    # ── Go 提取 ────────────────────────────────

    def _extract_go_imports(self, content: str) -> list[ImportInfo]:
        clean = self._strip_comments(content)
        imports = []
        for m in re.finditer(r'import\s+"([^"]+)"', clean):
            pkg = m.group(1)
            imports.append(ImportInfo(
                variable_name=pkg.rsplit("/", 1)[-1],
                source_module=pkg,
                import_type="named",
            ))
        for m in re.finditer(r'import\s*\(\s*([^)]+)\)', clean):
            for pm in re.finditer(r'"([^"]+)"', m.group(1)):
                pkg = pm.group(1)
                imports.append(ImportInfo(
                    variable_name=pkg.rsplit("/", 1)[-1],
                    source_module=pkg,
                    import_type="named",
                ))
        return imports

    def _extract_go_functions(self, content: str) -> list[FunctionSignature]:
        clean = self._strip_comments(content)
        funcs = []
        for m in re.finditer(
            r'func\s+(\w+)\s*\(([^)]*)\)\s*((?:\([^)]*\)|\S+)?)',
            clean,
        ):
            name = m.group(1)
            params = []
            for p in m.group(2).split(","):
                p = p.strip()
                if p:
                    parts = p.rsplit(None, 1)
                    params.append({"name": parts[0], "type": parts[1] if len(parts) == 2 else "unknown"})
            funcs.append(FunctionSignature(
                name=name,
                params=params,
                return_type=m.group(3).strip() or "unknown",
                is_exported=name[0].isupper() if name else False,
            ))
        return funcs

    def _extract_go_classes(self, content: str) -> list[ClassDefinition]:
        clean = self._strip_comments(content)
        classes = []
        for m in re.finditer(r'type\s+(\w+)\s+(struct|interface)\s*\{', clean):
            classes.append(ClassDefinition(
                name=m.group(1),
                methods=[],
                is_exported=m.group(1)[0].isupper(),
            ))
        return classes

    def _extract_go_exports(self, content: str) -> list[ExportInfo]:
        clean = self._strip_comments(content)
        exports = []
        seen = set()
        for m in re.finditer(r'func\s+([A-Z]\w*)\s*\(', clean):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                exports.append(ExportInfo(variable_name=name, is_function=True))
        for m in re.finditer(r'type\s+([A-Z]\w*)\s+(struct|interface)\s*\{', clean):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                exports.append(ExportInfo(variable_name=name, is_class=True))
        for m in re.finditer(r'(?:var|const)\s+([A-Z]\w*)\s*[=\[\{]', clean):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                exports.append(ExportInfo(variable_name=name))
        return exports

    def _extract_go_calls(self, content: str) -> list[FunctionCall]:
        clean = self._strip_comments(content)
        _go_builtins = {'if','for','switch','return','func','len','make','append',
                        'new','cap','close','delete','panic','recover','print','println',
                        'go','defer','range','select','case','map','chan','type','import','package'}
        return self._extract_generic_calls(clean, _go_builtins)

    # ── Java/Kotlin 提取 ──────────────────────

    def _extract_java_imports(self, content: str) -> list[ImportInfo]:
        clean = self._strip_comments(content)
        imports = []
        for m in re.finditer(r'import\s+(static\s+)?([\w.*]+)[ \t]*;?', clean):
            full = m.group(2)
            name = full.rsplit(".", 1)[-1]
            imports.append(ImportInfo(
                variable_name=name if name != "*" else full.rsplit(".", 1)[0],
                source_module=full,
                import_type="static" if m.group(1) else "named",
            ))
        return imports

    def _extract_java_functions(self, content: str) -> list[FunctionSignature]:
        clean = self._strip_comments(content)
        funcs = []
        # Java: public static ReturnType name(params) {
        for m in re.finditer(
            r'(?:public|private|protected)\s+(?:static\s+)?(?:final\s+)?'
            r'(?:<[^>]*>\s*)?(\w+(?:\[\])?(?:\s*<[^>]*>)?)\s+(\w+)\s*\(([^)]*)\)',
            clean,
        ):
            rtype, name, pstr = m.group(1), m.group(2), m.group(3)
            params = []
            for p in pstr.split(","):
                p = p.strip()
                if p:
                    parts = p.strip().split()
                    params.append({"name": parts[-1] if parts else p,
                                   "type": " ".join(parts[:-1]) if len(parts) > 1 else p})
            funcs.append(FunctionSignature(
                name=name, params=params, return_type=rtype,
                is_exported=True,  # public = exported
            ))
        # Kotlin: fun name(params): Type {
        for m in re.finditer(r'fun\s+(\w+)\s*\(([^)]*)\)\s*(?::\s*(\S+))?', clean):
            name, pstr, rtype = m.group(1), m.group(2), m.group(3) or "Unit"
            params = []
            for p in pstr.split(","):
                p = p.strip()
                if p:
                    if ":" in p:
                        pname, _, ptype = p.partition(":")
                        params.append({"name": pname.strip(), "type": ptype.strip() or "unknown"})
                    else:
                        params.append({"name": p, "type": "unknown"})
            funcs.append(FunctionSignature(
                name=name, params=params, return_type=rtype,
                is_exported=True,  # Kotlin default is public
            ))
        return funcs

    def _extract_java_classes(self, content: str) -> list[ClassDefinition]:
        clean = self._strip_comments(content)
        classes = []
        # Java: public class Name / class Name
        for m in re.finditer(
            r'(?:public|private|protected|abstract|final)\s+'
            r'(?:static\s+)?class\s+(\w+)',
            clean,
        ):
            classes.append(ClassDefinition(
                name=m.group(1), methods=[], is_exported=True,
            ))
        # Simple class without modifier (package-private)
        for m in re.finditer(r'(?<!\w)(?:class|interface)\s+(\w+)', clean):
            if not any(c.name == m.group(1) for c in classes):
                classes.append(ClassDefinition(
                    name=m.group(1), methods=[], is_exported=False,
                ))
        # Kotlin: class/object/interface/data class/enum class
        for m in re.finditer(
            r'(?:data\s+|sealed\s+|enum\s+)?(?:class|object|interface)\s+(\w+)',
            clean,
        ):
            if not any(c.name == m.group(1) for c in classes):
                classes.append(ClassDefinition(
                    name=m.group(1), methods=[], is_exported=True,
                ))
        return classes

    def _extract_java_exports(self, content: str) -> list[ExportInfo]:
        clean = self._strip_comments(content)
        exports = []
        seen = set()
        # Java public methods
        for m in re.finditer(
            r'public\s+(?:static\s+)?(?:final\s+)?\w+(?:<[^>]*>)?\s+(\w+)\s*\(', clean):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                exports.append(ExportInfo(variable_name=name, is_function=True))
        # Java public classes
        for m in re.finditer(r'public\s+class\s+(\w+)', clean):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                exports.append(ExportInfo(variable_name=name, is_class=True))
        # Kotlin fun/class (default public)
        for m in re.finditer(r'fun\s+(\w+)\s*\(', clean):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                exports.append(ExportInfo(variable_name=name, is_function=True))
        return exports

    def _extract_java_calls(self, content: str) -> list[FunctionCall]:
        clean = self._strip_comments(content)
        _java_keywords = {'if','else','while','for','switch','case','return','throw',
                          'new','try','catch','finally','import','package','class',
                          'synchronized','instanceof','super','this','break','continue'}
        return self._extract_generic_calls(clean, _java_keywords)

    # ── C/C++ 提取 ────────────────────────────

    def _extract_c_imports(self, content: str) -> list[ImportInfo]:
        clean = self._strip_comments(content)
        imports = []
        # #include <foo.h> and #include "foo.h"
        for m in re.finditer(r'#include\s+[<"]([^>"]+)[>"]', clean):
            path = m.group(1)
            name = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].rsplit(".", 1)[0]
            imports.append(ImportInfo(
                variable_name=name, source_module=path, import_type="include",
            ))
        # C++ using namespace / using declarations
        for m in re.finditer(r'using\s+(?:namespace\s+)?([\w:]+)\s*;', clean):
            name = m.group(1).split("::")[-1]
            imports.append(ImportInfo(
                variable_name=name, source_module=m.group(1), import_type="using",
            ))
        return imports

    _C_KEYWORDS = {'if','else','while','for','switch','case','return','goto',
                   'sizeof','break','continue','default','do','typedef','extern',
                   'static','const','volatile','register','auto','struct','enum','union'}

    def _extract_c_functions(self, content: str) -> list[FunctionSignature]:
        clean = self._strip_comments(content)
        funcs = []
        for m in re.finditer(
            # Return type + name(params) { or ; — multiline aware
            r'^\s*((?:(?:const|unsigned|signed|volatile|static|inline|extern|virtual)\s+)*'
            r'(?:\w+(?:::)?\s*(?:\*|\&)*\s*)+?)(\w+)\s*\(([^)]*)\)\s*(?:const\s*)?[\{;]',
            clean, re.MULTILINE,
        ):
            name = m.group(2)
            if name in self._C_KEYWORDS or name.startswith("_"):
                continue
            rtype = m.group(1).strip()
            is_static = 'static' in m.group(1)
            # Parse C-style params: Type name, Type2 name2
            params = []
            for p in m.group(3).split(","):
                p = p.strip()
                if not p or p == "void":
                    continue
                parts = p.strip().split()
                if parts:
                    params.append({"name": parts[-1].lstrip("*"),
                                   "type": " ".join(parts[:-1]) if len(parts) > 1 else "unknown"})
            funcs.append(FunctionSignature(
                name=name, params=params, return_type=rtype,
                is_exported=not is_static,
            ))
        return funcs

    def _extract_c_classes(self, content: str) -> list[ClassDefinition]:
        clean = self._strip_comments(content)
        classes = []
        seen = set()
        # C struct/union/enum and C++ class/struct
        for m in re.finditer(r'(?:typedef\s+)?(?:struct|union|enum|class)\s+(\w+)\s*(?::[^{]*)?\{', clean):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                classes.append(ClassDefinition(
                    name=name, methods=[], is_exported=True,
                ))
        return classes

    def _extract_c_exports(self, content: str) -> list[ExportInfo]:
        clean = self._strip_comments(content)
        exports = []
        seen = set()
        # Non-static function declarations/prototypes
        for m in re.finditer(
            r'^\s*(?:const\s+)?(?:\w+(?:::)?\s*(?:\*|\&)*\s+)+\**(\w+)\s*\([^)]*\)\s*;',
            clean, re.MULTILINE,
        ):
            name = m.group(1)
            if name not in self._C_KEYWORDS and name not in seen:
                seen.add(name)
                exports.append(ExportInfo(variable_name=name, is_function=True))
        return exports

    def _extract_c_calls(self, content: str) -> list[FunctionCall]:
        clean = self._strip_comments(content)
        return self._extract_generic_calls(clean, self._C_KEYWORDS)

    # ── C# 提取 ───────────────────────────────

    def _extract_cs_imports(self, content: str) -> list[ImportInfo]:
        clean = self._strip_comments(content)
        imports = []
        for m in re.finditer(r'using\s+(static\s+)?([\w.]+)\s*;', clean):
            full = m.group(2)
            name = full.rsplit(".", 1)[-1]
            imports.append(ImportInfo(
                variable_name=name, source_module=full,
                import_type="using_static" if m.group(1) else "using",
            ))
        return imports

    def _extract_cs_functions(self, content: str) -> list[FunctionSignature]:
        clean = self._strip_comments(content)
        funcs = []
        for m in re.finditer(
            r'(?:public|private|protected|internal)\s+(?:static\s+)?'
            r'(?:async\s+)?(?:virtual\s+|override\s+|abstract\s+)?'
            r'(\w+(?:<[^>]*>)?)\s+(\w+)\s*\(([^)]*)\)',
            clean,
        ):
            rtype, name, pstr = m.group(1), m.group(2), m.group(3)
            params = []
            for p in pstr.split(","):
                p = p.strip()
                if p:
                    parts = p.strip().split()
                    params.append({"name": parts[-1] if parts else p,
                                   "type": " ".join(parts[:-1]) if len(parts) > 1 else "unknown"})
            funcs.append(FunctionSignature(
                name=name, params=params, return_type=rtype, is_exported=True,
            ))
        return funcs

    def _extract_cs_classes(self, content: str) -> list[ClassDefinition]:
        clean = self._strip_comments(content)
        classes = []
        for m in re.finditer(
            r'(?:public|private|protected|internal)\s+(?:static\s+)?'
            r'(?:abstract\s+|sealed\s+|partial\s+)?(?:class|struct|interface|enum|record)\s+(\w+)',
            clean,
        ):
            classes.append(ClassDefinition(
                name=m.group(1), methods=[], is_exported=True,
            ))
        return classes

    def _extract_cs_exports(self, content: str) -> list[ExportInfo]:
        clean = self._strip_comments(content)
        exports = []
        seen = set()
        for m in re.finditer(
            r'public\s+(?:static\s+)?\w+(?:<[^>]*>)?\s+(\w+)\s*\(', clean):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                exports.append(ExportInfo(variable_name=name, is_function=True))
        for m in re.finditer(r'public\s+(?:class|struct|interface|enum|record)\s+(\w+)', clean):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                exports.append(ExportInfo(variable_name=name, is_class=True))
        return exports

    def _extract_cs_calls(self, content: str) -> list[FunctionCall]:
        clean = self._strip_comments(content)
        _cs_keywords = {'if','else','while','for','foreach','switch','case','return',
                        'throw','new','try','catch','finally','using','namespace','class',
                        'typeof','sizeof','is','as','lock','break','continue','in','out','ref'}
        return self._extract_generic_calls(clean, _cs_keywords)

    # ── Rust 提取 ─────────────────────────────

    def _extract_rust_imports(self, content: str) -> list[ImportInfo]:
        clean = self._strip_comments(content)
        imports = []
        # use std::collections::HashMap;
        for m in re.finditer(r'use\s+([\w:]+(?:\s*::\s*\{[^}]*\})?)\s*;', clean):
            full = m.group(1)
            name = full.split("::")[-1].strip()
            imports.append(ImportInfo(
                variable_name=name, source_module=full, import_type="use",
            ))
        # mod name;
        for m in re.finditer(r'mod\s+(\w+)\s*;', clean):
            imports.append(ImportInfo(
                variable_name=m.group(1), source_module=m.group(1), import_type="mod",
            ))
        return imports

    def _extract_rust_functions(self, content: str) -> list[FunctionSignature]:
        clean = self._strip_comments(content)
        funcs = []
        for m in re.finditer(
            r'(pub(?:\(\w+\))?\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+(\w+)'
            r'\s*(?:<[^>]*>)?\s*\(([^)]*)\)\s*(?:->\s*([^{;]+))?',
            clean,
        ):
            is_pub = bool(m.group(1))
            name = m.group(2)
            rtype = (m.group(4) or "()").strip()
            params = []
            for p in m.group(3).split(","):
                p = p.strip()
                if not p or p == "self" or p == "&self" or p == "&mut self":
                    continue
                if ":" in p:
                    pname, _, ptype = p.partition(":")
                    params.append({"name": pname.strip(), "type": ptype.strip() or "unknown"})
                else:
                    params.append({"name": p, "type": "unknown"})
            funcs.append(FunctionSignature(
                name=name, params=params, return_type=rtype, is_exported=is_pub,
            ))
        return funcs

    def _extract_rust_classes(self, content: str) -> list[ClassDefinition]:
        clean = self._strip_comments(content)
        classes = []
        for m in re.finditer(
            r'(pub(?:\(\w+\))?\s+)?(struct|enum|trait|impl)\s+(\w+)',
            clean,
        ):
            class_type = m.group(2)
            if class_type == "impl":
                continue  # impl blocks are method implementations, not type definitions
            classes.append(ClassDefinition(
                name=m.group(3), methods=[], is_exported=bool(m.group(1)),
            ))
        return classes

    def _extract_rust_exports(self, content: str) -> list[ExportInfo]:
        clean = self._strip_comments(content)
        exports = []
        seen = set()
        for m in re.finditer(r'pub(?:\s*\(\w+\))?\s+fn\s+(\w+)\s*[<\(]', clean):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                exports.append(ExportInfo(variable_name=name, is_function=True))
        for m in re.finditer(r'pub(?:\(\w+\))?\s+(struct|enum|trait|type)\s+(\w+)', clean):
            name = m.group(2)
            if name not in seen:
                seen.add(name)
                exports.append(ExportInfo(variable_name=name, is_class=(m.group(1) != "type")))
        return exports

    def _extract_rust_calls(self, content: str) -> list[FunctionCall]:
        clean = self._strip_comments(content)
        _rust_builtins = {'if','else','while','for','loop','match','return','let',
                          'fn','struct','enum','trait','impl','mod','use','pub','self',
                          'super','crate','unsafe','async','await','move','ref','mut','in'}
        return self._extract_generic_calls(clean, _rust_builtins)

    # ── Ruby 提取 ─────────────────────────────

    def _extract_ruby_imports(self, content: str) -> list[ImportInfo]:
        clean = content  # Ruby uses # comments, not //
        imports = []
        for m in re.finditer(r'require(?:_relative)?\s+["\']([^"\']+)["\']', clean):
            imports.append(ImportInfo(
                variable_name=m.group(1), source_module=m.group(1), import_type="require",
            ))
        for m in re.finditer(r'(?:include|extend|prepend)\s+(\w+(?:\s*,\s*\w+)*)', clean):
            for mod in m.group(1).split(","):
                mod = mod.strip()
                if mod:
                    imports.append(ImportInfo(
                        variable_name=mod, source_module=mod, import_type="mixin",
                    ))
        return imports

    def _extract_ruby_functions(self, content: str) -> list[FunctionSignature]:
        clean = content
        funcs = []
        for m in re.finditer(
            r'def\s+(?:self\.)?(\w+[?!]?)(?:\(([^)]*)\))?',
            clean,
        ):
            name = m.group(1)
            pstr = m.group(2) or ""
            params = []
            for p in pstr.split(","):
                p = p.strip()
                if p:
                    if ":" in p:
                        pname, _, pdefault = p.partition(":")
                        params.append({"name": pname.strip(), "type": "unknown"})
                    elif "=" in p:
                        pname, _, _ = p.partition("=")
                        params.append({"name": pname.strip(), "type": "unknown"})
                    else:
                        params.append({"name": p, "type": "unknown"})
            funcs.append(FunctionSignature(
                name=name, params=params, return_type="unknown",
                is_exported=not name.startswith("_"),
            ))
        return funcs

    def _extract_ruby_classes(self, content: str) -> list[ClassDefinition]:
        clean = content
        classes = []
        for m in re.finditer(r'(?:class|module)\s+(\w+(?:::)?\w*)', clean):
            classes.append(ClassDefinition(
                name=m.group(1), methods=[], is_exported=True,
            ))
        return classes

    def _extract_ruby_exports(self, content: str) -> list[ExportInfo]:
        clean = content
        exports = []
        seen = set()
        for m in re.finditer(r'def\s+(?:self\.)?(\w+[?!]?)', clean):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                exports.append(ExportInfo(variable_name=name, is_function=True))
        for m in re.finditer(r'(?:class|module)\s+(\w+)', clean):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                exports.append(ExportInfo(variable_name=name, is_class=True))
        return exports

    def _extract_ruby_calls(self, content: str) -> list[FunctionCall]:
        _ruby_keywords = {'if','unless','while','until','for','case','when','begin',
                          'end','def','class','module','do','return','break','next',
                          'redo','retry','super','yield','raise','rescue','ensure','self'}
        return self._extract_generic_calls(content, _ruby_keywords)

    # ── Swift 提取 ────────────────────────────

    def _extract_swift_imports(self, content: str) -> list[ImportInfo]:
        clean = self._strip_comments(content)
        imports = []
        for m in re.finditer(r'import\s+(\w+)', clean):
            imports.append(ImportInfo(
                variable_name=m.group(1), source_module=m.group(1), import_type="named",
            ))
        return imports

    def _extract_swift_functions(self, content: str) -> list[FunctionSignature]:
        clean = self._strip_comments(content)
        funcs = []
        for m in re.finditer(
            r'(?:public|open|private|internal|fileprivate)\s+'
            r'(?:static\s+)?(?:override\s+)?(?:mutating\s+)?'
            r'func\s+(\w+)\s*\(([^)]*)\)\s*(?:throws\s+)?(?:async\s+)?'
            r'(?:->\s*(\S+))?',
            clean,
        ):
            name, pstr, rtype = m.group(1), m.group(2), (m.group(3) or "Void").strip()
            params = []
            for p in pstr.split(","):
                p = p.strip()
                if not p or p == "_":
                    continue
                if ":" in p:
                    # label pname: Type
                    parts = p.split(":", 1)
                    pname = parts[0].strip()
                    ptype = parts[1].strip() if len(parts) > 1 else "unknown"
                    params.append({"name": pname, "type": ptype})
                else:
                    params.append({"name": p, "type": "unknown"})
            funcs.append(FunctionSignature(
                name=name, params=params, return_type=rtype, is_exported=True,
            ))
        return funcs

    def _extract_swift_classes(self, content: str) -> list[ClassDefinition]:
        clean = self._strip_comments(content)
        classes = []
        # Classes with visibility modifiers
        for m in re.finditer(
            r'(?:public|open|private|internal|fileprivate)\s+'
            r'(?:final\s+)?(class|struct|enum|protocol|extension)\s+(\w+)',
            clean,
        ):
            classes.append(ClassDefinition(
                name=m.group(2), methods=[], is_exported=True,
            ))
        # Classes without visibility modifiers (internal by default)
        for m in re.finditer(
            r'(?:final\s+)?(class|struct|enum|protocol|extension)\s+(\w+)',
            clean,
        ):
            if not any(c.name == m.group(2) for c in classes):
                classes.append(ClassDefinition(
                    name=m.group(2), methods=[], is_exported=True,
                ))
        return classes

    def _extract_swift_exports(self, content: str) -> list[ExportInfo]:
        clean = self._strip_comments(content)
        exports = []
        seen = set()
        for m in re.finditer(
            r'(?:public|open)\s+(?:static\s+)?func\s+(\w+)\s*\(', clean):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                exports.append(ExportInfo(variable_name=name, is_function=True))
        for m in re.finditer(
            r'(?:public|open)\s+(?:final\s+)?(class|struct|enum|protocol)\s+(\w+)', clean):
            name = m.group(2)
            if name not in seen:
                seen.add(name)
                exports.append(ExportInfo(variable_name=name, is_class=True))
        return exports

    def _extract_swift_calls(self, content: str) -> list[FunctionCall]:
        clean = self._strip_comments(content)
        _swift_keywords = {'if','else','guard','while','for','switch','case','return',
                           'throw','try','catch','import','class','struct','enum','protocol',
                           'extension','func','let','var','defer','break','continue','where',
                           'default','fallthrough','repeat','do','associatedtype','typealias'}
        return self._extract_generic_calls(clean, _swift_keywords)

    # ── TS/JS 调用提取 ────────────────────────

    def _extract_ts_calls(self, content: str) -> list[FunctionCall]:
        clean = self._strip_comments(content)
        _ts_keywords = {'if','else','while','for','switch','case','return','throw',
                        'new','try','catch','finally','import','export','typeof',
                        'instanceof','delete','break','continue','function','class',
                        'async','await','yield','default','from','of','in','void'}
        return self._extract_generic_calls(clean, _ts_keywords)

    # ── Vue/Svelte ────────────────────────────

    def _extract_vue_svelte_script(self, content: str) -> str | None:
        # Match <script ...>...</script> or <script setup ...>...</script>
        m = re.search(r'<script[^>]*>([\s\S]*?)</script>', content)
        return m.group(1) if m else None

    # ── Bash 提取 ─────────────────────────────

    def _extract_bash_imports(self, content: str) -> list[ImportInfo]:
        imports = []
        for m in re.finditer(r'(?:^|\n)\s*(?:source|\.)\s+([^\s;|&]+)', content):
            imports.append(ImportInfo(
                variable_name=m.group(1).strip(), source_module=m.group(1).strip(),
                import_type="source",
            ))
        return imports

    def _extract_bash_functions(self, content: str) -> list[FunctionSignature]:
        funcs = []
        # function name() { ... }  and  name() { ... }
        for m in re.finditer(r'(?:function\s+)?(\w+)\s*\(\s*\)\s*\{', content):
            name = m.group(1)
            if name in {'if','then','else','elif','fi','for','while','until',
                        'do','done','case','esac','select','in','function'}:
                continue
            funcs.append(FunctionSignature(
                name=name, params=[], return_type="unknown", is_exported=True,
            ))
        return funcs

    def _extract_bash_exports(self, content: str) -> list[ExportInfo]:
        exports = []
        for m in re.finditer(r'(?:function\s+)?(\w+)\s*\(\s*\)\s*\{', content):
            name = m.group(1)
            if name not in {'if','then','else','elif','fi','for','while',
                            'until','do','done','case','esac','function'}:
                exports.append(ExportInfo(variable_name=name, is_function=True))
        return exports

    # ── 通用辅助 ──────────────────────────────

    def _strip_comments(self, content: str) -> str:
        """Remove // line comments and /* */ block comments."""
        content = re.sub(r'//[^\n]*', '', content)
        content = re.sub(r'/\*[\s\S]*?\*/', '', content)
        return content

    def _extract_generic_calls(
        self, content: str, keyword_set: set[str] | frozenset[str],
    ) -> list[FunctionCall]:
        """Extract function calls by regex, skipping known keywords.

        Matches patterns like: foo(args), obj.foo(args), pkg::foo(args)
        """
        calls = []
        for m in re.finditer(r'(\w+(?:\.\w+|::\w+)*)\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)', content):
            callee = m.group(1).strip()
            if callee in keyword_set:
                continue
            args_str = m.group(2)
            args = []
            for i, arg in enumerate(args_str.split(",")):
                arg = arg.strip()
                if arg:
                    args.append({"name": arg, "type": "unknown", "position": i})
            calls.append(FunctionCall(
                caller_name="", callee_name=callee, args=args, line=0,
            ))
        return calls

    # ── 参数解析辅助 ──────────────────────────

    def _parse_py_ast(self, content: str) -> ast.Module | None:
        try:
            return ast.parse(content)
        except SyntaxError:
            return None

    def _annotation_to_str(self, annotation) -> str:
        if annotation is None:
            return "unknown"
        try:
            return ast.unparse(annotation).strip()
        except Exception:
            return "unknown"

    def _parse_py_ast_params(self, args: ast.arguments, skip_self: bool = False) -> list[dict]:
        params: list[dict] = []

        def add_arg(arg: ast.arg, prefix: str = ""):
            name = f"{prefix}{arg.arg}"
            if skip_self and arg.arg in {"self", "cls"}:
                return
            params.append({"name": name, "type": self._annotation_to_str(arg.annotation)})

        for arg in args.posonlyargs:
            add_arg(arg)
        for arg in args.args:
            add_arg(arg)
        if args.vararg:
            add_arg(args.vararg, "*")
        for arg in args.kwonlyargs:
            add_arg(arg)
        if args.kwarg:
            add_arg(args.kwarg, "**")
        return params

    def _parse_ts_params(self, params_str: str) -> list[dict]:
        params = []
        if not params_str.strip():
            return params
        for p in params_str.split(","):
            p = p.strip()
            if not p:
                continue
            parts = p.split(":")
            name = parts[0].strip()
            ptype = parts[1].strip() if len(parts) > 1 else "unknown"
            # 处理默认值
            if "=" in ptype:
                ptype, default = ptype.split("=", 1)
                ptype = ptype.strip()
            params.append({"name": name, "type": ptype})
        return params

    def _parse_py_params(self, params_str: str) -> list[dict]:
        params = []
        if not params_str.strip():
            return params
        for p in params_str.split(","):
            p = p.strip()
            if not p or p == "self" or p == "cls":
                continue
            if ":" in p:
                name, ptype = p.split(":", 1)
                name = name.strip()
                if "=" in ptype:
                    ptype = ptype.split("=", 1)[0].strip()
                params.append({"name": name, "type": ptype.strip()})
            else:
                name = p.split("=")[0].strip()
                params.append({"name": name, "type": "unknown"})
        return params


# 单例
parser = CodeParser()
