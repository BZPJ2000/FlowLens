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

    SUPPORTED_LANGS = {"typescript", "javascript", "python", "go", "rust", "java"}

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
