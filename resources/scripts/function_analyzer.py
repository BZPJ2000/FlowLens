from __future__ import annotations

import argparse
import json
from pathlib import Path

from modules.static_flow import (
    AnalyzeProjectOptions,
    analyze_project,
    format_static_flow_report,
    format_static_flow_summary,
)


def analyze_target(
    target_path: str,
    *,
    details: bool = False,
    json_path: str | None = None,
    workers: int | None = None,
    max_file_size_kb: int | None = None,
    exclude_dirs: tuple[str, ...] = (),
    symbol_limit: int | None = 200,
) -> None:
    default_options = AnalyzeProjectOptions()
    options = AnalyzeProjectOptions(
        excluded_dir_names=default_options.excluded_dir_names | frozenset(exclude_dirs),
        max_file_size_kb=(
            max_file_size_kb
            if max_file_size_kb is not None
            else default_options.max_file_size_kb
        ),
        workers=workers if workers is not None else default_options.workers,
    )
    graph = analyze_project(Path(target_path), options=options)
    if json_path is not None:
        Path(json_path).write_text(
            json.dumps(graph.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if details:
        print(format_static_flow_report(graph))
    else:
        print(format_static_flow_summary(graph, symbol_limit=symbol_limit))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze a project directory and print its static function flow."
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Project directory to analyze. A single Python file is accepted for debugging.",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Print every symbol and flow edge. Default output is a project-level summary.",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        help="Write the full StaticProjectGraph payload to this JSON file.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        help="Concurrent parser workers. Defaults to a small CPU-based value.",
    )
    parser.add_argument(
        "--max-file-size-kb",
        type=int,
        help="Skip Python files larger than this size. Use 0 for no size limit.",
    )
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Directory name to exclude. Can be passed multiple times.",
    )
    parser.add_argument(
        "--limit-symbols",
        type=int,
        default=200,
        help="Maximum symbols shown in summary. Use 0 for no limit.",
    )
    args = parser.parse_args()

    analyze_target(
        args.target,
        details=args.details,
        json_path=args.json_path,
        workers=args.workers,
        max_file_size_kb=args.max_file_size_kb,
        exclude_dirs=tuple(args.exclude_dir),
        symbol_limit=None if args.limit_symbols == 0 else args.limit_symbols,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
