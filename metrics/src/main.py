"""Static-metrics orchestrator: the 9-metric cognitive-load matrix as tables.

Fans one directory of Python files out to every analyzer and emits two
research-ready tables (FR-INST-4):

- ``function_metrics``: one row per (file, function) - the tree-sitter four
  plus Halstead effort.
- ``file_metrics``: one row per file - indentation variance, line-width
  bounds, comment ratio, total Halstead effort, SonarQube cognitive
  complexity (NaN while the server is stubbed, decision D5).

Every row is stamped with the join keys ``participantId``, ``condition``,
``sessionId``, a capture timestamp, and ``schemaVersion`` so metrics rows
join the other legs on one timeline (FR-INST-6). ``--format jsonl`` mirrors
the CSV rows as JSON Lines for middleware ingestion.

Run from the repo root:
    uv run python metrics/src/main.py [target_dir] --participant P00 ...
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyzers.radon_metrics import get_comment_ratio, get_halstead_effort  # noqa: E402
from analyzers.sonar_metrics import get_cognitive_complexity  # noqa: E402
from analyzers.text_metrics import (  # noqa: E402
    get_indentation_variance,
    get_line_width_bounds,
)
from parsers.ts_parser import collect_function_metrics  # noqa: E402

#: Bump on any change to row shape or column meaning (NFR-4).
SCHEMA_VERSION = 1

DEFAULT_TARGET = Path(__file__).resolve().parents[1] / "corpus"
SKIP_DIRS = {"venv", ".venv", "__pycache__", "node_modules", ".git"}


def discover_python_files(target: Path) -> list[Path]:
    return sorted(
        p
        for p in target.rglob("*.py")
        if not any(part in SKIP_DIRS for part in p.parts)
    )


def analyze_file(path: Path, target: Path, sonar_url: str) -> tuple[list[dict], dict]:
    """All metrics for one file: (function rows, file row), join keys not
    yet stamped. Halstead efforts are joined to tree-sitter rows by function
    name; a name that appears twice in one file (same-named methods in two
    classes) keeps its first occurrence - a known limitation, rare in
    practice and acceptable for the corpus (see implementation plan §5)."""
    source_bytes = path.read_bytes()
    source = source_bytes.decode("utf-8", errors="replace")
    rel_path = path.relative_to(target).as_posix()

    halstead = get_halstead_effort(source)
    function_rows = [
        {
            "file": rel_path,
            "function": name,
            **row,
            "halstead_effort": halstead["functions"].get(name),
        }
        for name, row in sorted(collect_function_metrics(source_bytes).items())
    ]

    widths = get_line_width_bounds(source)
    file_row = {
        "file": rel_path,
        "indentation_variance": get_indentation_variance(source),
        "max_line_width": widths["max_line_width"],
        "mean_line_width": widths["mean_line_width"],
        "comment_ratio": get_comment_ratio(source),
        "halstead_effort_total": halstead["total"],
        "cognitive_complexity": get_cognitive_complexity(rel_path, sonar_url),
    }
    return function_rows, file_row


def build_tables(
    target: Path,
    join_keys: dict,
    sonar_url: str = "http://localhost:9000",
    timestamp: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Analyze every Python file under ``target``; return the two tables,
    every row stamped with the join keys and a capture timestamp (given, or
    derived per file from its mtime)."""
    all_function_rows: list[dict] = []
    all_file_rows: list[dict] = []
    for path in discover_python_files(target):
        stamp = timestamp or datetime.fromtimestamp(
            path.stat().st_mtime, tz=UTC
        ).isoformat(timespec="seconds")
        keys = {**join_keys, "timestamp": stamp, "schemaVersion": SCHEMA_VERSION}
        function_rows, file_row = analyze_file(path, target, sonar_url)
        all_function_rows += [{**row, **keys} for row in function_rows]
        all_file_rows.append({**file_row, **keys})
    return pd.DataFrame(all_function_rows), pd.DataFrame(all_file_rows)


def write_tables(
    tables: dict[str, pd.DataFrame], out_dir: Path, fmt: str
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, df in tables.items():
        out = out_dir / f"{name}.{fmt}"
        if fmt == "csv":
            df.to_csv(out, index=False)
        else:  # jsonl: one JSON object per row, NaN -> null
            with out.open("w", encoding="utf-8") as fh:
                for record in df.to_dict(orient="records"):
                    clean = {k: (None if pd.isna(v) else v) for k, v in record.items()}
                    fh.write(json.dumps(clean) + "\n")
        written.append(out)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract the 9-metric cognitive-load matrix over a "
        "directory of Python files."
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=DEFAULT_TARGET,
        type=Path,
        help=f"directory to analyze (default: {DEFAULT_TARGET})",
    )
    parser.add_argument("--out", default=Path("results"), type=Path)
    parser.add_argument("--sonar-url", default="http://localhost:9000")
    parser.add_argument("--format", choices=["csv", "jsonl"], default="csv")
    parser.add_argument("--participant", default="unspecified")
    parser.add_argument("--condition", default="unspecified")
    parser.add_argument("--session", default="adhoc")
    parser.add_argument(
        "--timestamp",
        help="ISO capture timestamp for all rows (default: per-file mtime)",
    )
    args = parser.parse_args(argv)

    if not args.target.is_dir():
        print(f"error: target {args.target} is not a directory", file=sys.stderr)
        return 1

    join_keys = {
        "participantId": args.participant,
        "condition": args.condition,
        "sessionId": args.session,
    }
    function_df, file_df = build_tables(
        args.target, join_keys, args.sonar_url, args.timestamp
    )
    written = write_tables(
        {"function_metrics": function_df, "file_metrics": file_df},
        args.out,
        args.format,
    )

    print(
        f"Analyzed {len(file_df)} files, {len(function_df)} functions "
        f"under {args.target}"
    )
    for path in written:
        print(f"  wrote {path}")
    if not file_df.empty:
        print("\nFile-level summary:")
        print(
            file_df[
                [
                    "file",
                    "indentation_variance",
                    "max_line_width",
                    "comment_ratio",
                    "halstead_effort_total",
                ]
            ].to_string(index=False)
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
