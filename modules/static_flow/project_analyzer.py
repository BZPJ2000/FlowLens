from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from os import cpu_count
from time import perf_counter

from contracts.static_flow import StaticProjectGraph, StaticScanStats

from .python_adapter import ParsedPythonModule, build_python_static_graph
from .tree_sitter_adapter import (
    ParsedTreeSitterModule,
    build_tree_sitter_static_graph,
    parse_tree_sitter_file,
    supports_tree_sitter_suffix,
)

DEFAULT_EXCLUDED_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
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
)

DEFAULT_MAX_FILE_SIZE_KB = 1024
DEFAULT_WORKERS = max(1, min(8, cpu_count() or 1))
PYTHON_SUFFIXES = frozenset({".py"})
TREE_SITTER_SUFFIXES = frozenset({".ts", ".tsx", ".js", ".jsx"})
SUPPORTED_SUFFIXES = PYTHON_SUFFIXES | TREE_SITTER_SUFFIXES


@dataclass(frozen=True, kw_only=True)
class AnalyzeProjectOptions:
    excluded_dir_names: frozenset[str] = DEFAULT_EXCLUDED_DIR_NAMES
    max_file_size_kb: int = DEFAULT_MAX_FILE_SIZE_KB
    workers: int = DEFAULT_WORKERS


def analyze_project(
    project_path: str | Path,
    *,
    options: AnalyzeProjectOptions | None = None,
) -> StaticProjectGraph:
    options = options or AnalyzeProjectOptions()
    started = perf_counter()
    original_path = Path(project_path).resolve()
    root = original_path.parent if original_path.is_file() else original_path
    warnings: list[str] = []

    if not root.exists():
        return StaticProjectGraph(
            project_root=str(root),
            symbols=(),
            signatures=(),
            local_variables=(),
            edges=(),
            warnings=(f"Project target does not exist: {root}",),
            scan_stats=StaticScanStats(
                target_path=str(original_path),
                elapsed_ms=_elapsed_ms(started),
            ),
        )

    if original_path.is_file():
        file_paths = (original_path,) if _is_supported_source_file(original_path) else ()
        skipped_count = 0
    else:
        scan_result = _scan_source_files(root, options=options)
        file_paths = scan_result.file_paths
        skipped_count = scan_result.skipped_count
        if not file_paths:
            warnings.append(f"No supported source files were found under: {root}")

    python_paths = tuple(path for path in file_paths if path.suffix.lower() in PYTHON_SUFFIXES)
    tree_sitter_paths = tuple(
        path
        for path in file_paths
        if path.suffix.lower() in TREE_SITTER_SUFFIXES and supports_tree_sitter_suffix(path.suffix)
    )
    unsupported_tree_sitter_count = len(file_paths) - len(python_paths) - len(tree_sitter_paths)
    if unsupported_tree_sitter_count:
        skipped_count += unsupported_tree_sitter_count

    python_results = _parse_python_files(python_paths, workers=options.workers)
    python_modules = [result.module for result in python_results if result.module is not None]
    tree_results = _parse_tree_sitter_files(tree_sitter_paths, workers=options.workers)
    tree_modules = [result.tree_module for result in tree_results if result.tree_module is not None]

    failed_results = [
        *[result.error_message for result in python_results if result.error_message is not None],
        *[result.error_message for result in tree_results if result.error_message is not None],
    ]
    failed_count = len(failed_results)
    warnings.extend(message for message in failed_results if message)

    graph = _merge_graphs(
        root,
        (
            build_python_static_graph(root, tuple(python_modules)),
            build_tree_sitter_static_graph(root, tuple(tree_modules)),
        ),
    )
    return StaticProjectGraph(
        project_root=graph.project_root,
        symbols=graph.symbols,
        signatures=graph.signatures,
        local_variables=graph.local_variables,
        edges=graph.edges,
        warnings=tuple([*warnings, *graph.warnings]),
        scan_stats=StaticScanStats(
            target_path=str(original_path),
            files_discovered=len(file_paths),
            files_parsed=len(python_modules) + len(tree_modules),
            files_failed=failed_count,
            files_skipped=skipped_count,
            elapsed_ms=_elapsed_ms(started),
        ),
    )


@dataclass(frozen=True)
class _ScanResult:
    file_paths: tuple[Path, ...]
    skipped_count: int


@dataclass(frozen=True)
class _ParseResult:
    module: ParsedPythonModule | None = None
    tree_module: ParsedTreeSitterModule | None = None
    error_message: str | None = None


def _scan_source_files(root: Path, *, options: AnalyzeProjectOptions) -> _ScanResult:
    file_paths: list[Path] = []
    skipped_count = 0
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            children = list(directory.iterdir())
        except OSError:
            continue
        for path in children:
            if path.is_dir():
                if _should_skip_dir(path, options.excluded_dir_names):
                    skipped_count += 1
                    continue
                stack.append(path)
                continue
            if not path.is_file() or not _is_supported_source_file(path):
                continue
            if _is_too_large(path, options.max_file_size_kb):
                skipped_count += 1
                continue
            file_paths.append(path)
    file_paths.sort()
    return _ScanResult(file_paths=tuple(file_paths), skipped_count=skipped_count)


def _parse_python_files(file_paths: tuple[Path, ...], *, workers: int) -> tuple[_ParseResult, ...]:
    worker_count = max(1, workers)
    if worker_count == 1 or len(file_paths) <= 1:
        return tuple(_parse_python_file(file_path) for file_path in file_paths)
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        return tuple(executor.map(_parse_python_file, file_paths))


def _parse_python_file(file_path: Path) -> _ParseResult:
    try:
        source_text = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source_text, filename=str(file_path))
    except (OSError, SyntaxError) as exc:
        return _ParseResult(error_message=f"Could not parse {file_path}: {exc}")
    return _ParseResult(
        module=ParsedPythonModule(
            file_path=str(file_path),
            source_text=source_text,
            tree=tree,
        )
    )


def _parse_tree_sitter_files(file_paths: tuple[Path, ...], *, workers: int) -> tuple[_ParseResult, ...]:
    worker_count = max(1, workers)
    if worker_count == 1 or len(file_paths) <= 1:
        return tuple(_parse_tree_sitter_file(file_path) for file_path in file_paths)
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        return tuple(executor.map(_parse_tree_sitter_file, file_paths))


def _parse_tree_sitter_file(file_path: Path) -> _ParseResult:
    try:
        return _ParseResult(tree_module=parse_tree_sitter_file(file_path))
    except Exception as exc:
        return _ParseResult(error_message=f"Could not parse {file_path}: {exc}")


def _merge_graphs(root: Path, graphs: tuple[StaticProjectGraph, ...]) -> StaticProjectGraph:
    return StaticProjectGraph(
        project_root=str(root),
        symbols=tuple(symbol for graph in graphs for symbol in graph.symbols),
        signatures=tuple(signature for graph in graphs for signature in graph.signatures),
        local_variables=tuple(variable for graph in graphs for variable in graph.local_variables),
        edges=tuple(edge for graph in graphs for edge in graph.edges),
        warnings=tuple(warning for graph in graphs for warning in graph.warnings),
    )


def _should_skip_dir(path: Path, excluded_dir_names: frozenset[str]) -> bool:
    name = path.name
    return name in excluded_dir_names or name.startswith(".")


def _is_too_large(path: Path, max_file_size_kb: int) -> bool:
    if max_file_size_kb <= 0:
        return False
    try:
        return path.stat().st_size > max_file_size_kb * 1024
    except OSError:
        return True


def _elapsed_ms(started: float) -> int:
    return int((perf_counter() - started) * 1000)


def _is_supported_source_file(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_SUFFIXES
