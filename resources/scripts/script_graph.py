from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from modules.static_flow import analyze_project, export_static_flow_dot


def build_call_graph(file_path: str, output_path: str = "call_graph") -> None:
    graph = analyze_project(Path(file_path))
    dot_text = export_static_flow_dot(graph)
    dot_path = Path(output_path).with_suffix(".dot")
    dot_path.write_text(dot_text, encoding="utf-8")

    png_path = Path(output_path).with_suffix(".png")
    try:
        subprocess.run(
            ["dot", "-Tpng", str(dot_path), "-o", str(png_path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"DOT graph written: {dot_path}")
        print(f"PNG render skipped: Graphviz 'dot' failed ({exc}).")
        return

    print(f"DOT graph written: {dot_path}")
    print(f"PNG graph written: {png_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze a project directory and export its static function flow graph."
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Project directory to analyze. A single Python file is accepted for debugging.",
    )
    parser.add_argument(
        "output",
        nargs="?",
        default="project_flow",
        help="Output file base path without extension.",
    )
    args = parser.parse_args()

    build_call_graph(args.target, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
