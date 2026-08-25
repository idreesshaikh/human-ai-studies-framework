"""Static-metrics orchestrator: the 9-metric cognitive-load matrix as tables."""

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyzers.radon_metrics import get_comment_ratio, get_halstead_effort
from analyzers.sonar_metrics import get_cognitive_complexity
from analyzers.text_metrics import (
    get_indentation_variance,
    get_line_width_bounds,
)
from parsers.ts_parser import collect_function_metrics

SCHEMA_VERSION = 2

DEFAULT_TARGET = Path(__file__).resolve().parents[1] / "corpus"
SKIP_DIRS = {"venv", ".venv", "__pycache__", "node_modules", ".git"}
ALL_METRICS = "cognitive-load-9"


def discover_python_files(target: Path) -> list[Path]:
    return sorted(
        p
        for p in target.rglob("*.py")
        if not any(part in SKIP_DIRS for part in p.parts)
    )


def analyze_file(path: Path, target: Path, sonar_url: str) -> tuple[list[dict], dict]:
    """
    All metrics for one file: (function rows, file row), join keys not yet stamped.
    """
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
    cognitive_complexity = get_cognitive_complexity(rel_path, sonar_url)
    file_row = {
        "file": rel_path,
        "indentation_variance": get_indentation_variance(source),
        "max_line_width": widths["max_line_width"],
        "mean_line_width": widths["mean_line_width"],
        "comment_ratio": get_comment_ratio(source),
        "halstead_effort_total": halstead["total"],
        "cognitive_complexity": cognitive_complexity,
        "sonarStatus": "available" if cognitive_complexity is not None else "degraded",
    }
    return function_rows, file_row


def build_tables(
    target: Path,
    join_keys: dict,
    sonar_url: str = "http://localhost:9000",
    timestamp: str | None = None,
    metric_run_id: str = "",
    metric_run_status: str = "ok",
    metric_run_timestamp: str | None = None,
    metric_set: str | list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Analyze every Python file under ``target``; return the two tables, every row stamped
    with the join keys and a capture timestamp (given, or derived per file from its
    mtime).
    """
    all_function_rows: list[dict] = []
    all_file_rows: list[dict] = []
    metric_set_value = metric_set or ALL_METRICS
    for path in discover_python_files(target):
        stamp = timestamp or datetime.fromtimestamp(
            path.stat().st_mtime, tz=UTC
        ).isoformat(timespec="seconds")
        keys = {
            **join_keys,
            "source": "metrics",
            "timestamp": stamp,
            "schemaVersion": SCHEMA_VERSION,
            "metricRunId": metric_run_id,
            "metricRunStatus": metric_run_status,
            "metricRunTimestamp": metric_run_timestamp or stamp,
            "metricSet": metric_set_value,
        }
        function_rows, file_row = analyze_file(path, target, sonar_url)
        for row in function_rows:
            stamped = {**row, **keys}
            stamped["metricId"] = _metric_id("function_metrics", stamped)
            all_function_rows.append(stamped)
        stamped_file = {**file_row, **keys}
        stamped_file["metricId"] = _metric_id("file_metrics", stamped_file)
        all_file_rows.append(stamped_file)
    function_df = pd.DataFrame(all_function_rows)
    file_df = pd.DataFrame(all_file_rows)
    if metric_set_value != ALL_METRICS:
        selected = (
            {metric_set_value}
            if isinstance(metric_set_value, str)
            else set(metric_set_value)
        )
        common = {
            "file",
            "participantId",
            "condition",
            "sessionId",
            "taskId",
            "source",
            "timestamp",
            "schemaVersion",
            "metricRunId",
            "metricRunStatus",
            "metricRunTimestamp",
            "metricSet",
            "metricId",
        }
        function_columns = common | {"function"} | selected
        function_df = function_df[
            [column for column in function_df.columns if column in function_columns]
        ]
        file_df = file_df[
            [column for column in file_df.columns if column in common | selected]
        ]
    return function_df, file_df


def _metric_id(table: str, row: dict) -> str:
    """Stable identity for idempotent replay, with no source-code content."""
    identity = "|".join(
        str(row.get(key, ""))
        for key in (
            "sessionId",
            "participantId",
            "condition",
            "taskId",
            "file",
            "function",
            "schemaVersion",
            "metricSet",
        )
    )
    return sha256(f"{table}|{identity}".encode()).hexdigest()[:24]


def _load_manifest(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("session manifest must be an object")
    return value


def post_rows(rows: list[dict], endpoint: str, timeout: float = 10.0) -> dict:
    """Best-effort metrics mirror. Local output remains the recovery source."""
    if not rows:
        return {"received": 0, "inserted": 0, "duplicates": 0, "error": None}
    if not endpoint:
        return {
            "received": len(rows),
            "inserted": 0,
            "duplicates": 0,
            "error": "no metrics endpoint",
        }
    if urlsplit(endpoint).scheme not in {"http", "https"}:
        return {
            "received": len(rows),
            "inserted": 0,
            "duplicates": 0,
            "error": "metrics endpoint must use http or https",
        }
    request = urllib.request.Request(  # noqa: S310 - endpoint scheme is checked above
        endpoint,
        data=json.dumps(rows, allow_nan=False).encode(),
        method="POST",
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return json.loads(response.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        return {
            "received": len(rows),
            "inserted": 0,
            "duplicates": 0,
            "error": str(exc),
        }


def _clean_record(record: dict) -> dict:
    """Convert pandas missing scalars to JSON null before an HTTP upload."""
    return {key: (None if pd.isna(value) else value) for key, value in record.items()}


def write_tables(
    tables: dict[str, pd.DataFrame], out_dir: Path, fmt: str
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, df in tables.items():
        out = out_dir / f"{name}.{fmt}"
        if fmt == "csv":
            df.to_csv(out, index=False)
        else:
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
        default=None,
        type=Path,
        help=f"directory to analyze (default: {DEFAULT_TARGET})",
    )
    parser.add_argument("--out", default=Path("results"), type=Path)
    parser.add_argument("--sonar-url", default="http://localhost:9000")
    parser.add_argument("--format", choices=["csv", "jsonl"], default="csv")
    parser.add_argument("--participant", default="unspecified")
    parser.add_argument("--condition", default="unspecified")
    parser.add_argument("--session", default="adhoc")
    parser.add_argument("--task-id", default="")
    parser.add_argument("--manifest", type=Path, help="prepared session manifest")
    parser.add_argument(
        "--post",
        action="store_true",
        help="POST metric rows to the manifest metrics endpoint",
    )
    parser.add_argument("--metrics-endpoint", default="")
    parser.add_argument(
        "--timestamp",
        help="ISO capture timestamp for all rows (default: per-file mtime)",
    )
    args = parser.parse_args(argv)

    manifest = _load_manifest(args.manifest) if args.manifest else {}
    manifest_workspace = (manifest.get("runner") or {}).get("workspace", "")
    target = args.target or (
        Path(manifest_workspace) if manifest_workspace else DEFAULT_TARGET
    )
    if not target.is_dir():
        print(f"error: target {target} is not a directory", file=sys.stderr)
        return 1

    join_keys = {
        "participantId": manifest.get("participantId", args.participant),
        "condition": manifest.get("condition", args.condition),
        "sessionId": manifest.get("sessionId", args.session),
        "taskId": manifest.get("taskId", args.task_id),
    }
    metrics_config = (manifest.get("producers") or {}).get("metrics") or {}
    metric_set = metrics_config.get("metricSet", ALL_METRICS)
    if not isinstance(metric_set, (str, list)):
        metric_set = ALL_METRICS
    run_stamp = datetime.now(UTC).isoformat(timespec="milliseconds")
    run_id = f"metrics-{run_stamp.replace(':', '').replace('+00:00', 'Z')}"
    function_df, file_df = build_tables(
        target,
        join_keys,
        args.sonar_url,
        args.timestamp,
        metric_run_id=run_id,
        metric_run_timestamp=run_stamp,
        metric_set=metric_set,
    )
    if not file_df.empty and (file_df["sonarStatus"] == "degraded").any():
        metric_run_status = "degraded-sonar"
        for frame in (function_df, file_df):
            frame["metricRunStatus"] = metric_run_status
        print(
            "warning: SonarQube cognitive complexity is unavailable; "
            "local metrics were retained with metricRunStatus=degraded-sonar",
            file=sys.stderr,
        )
    written = write_tables(
        {"function_metrics": function_df, "file_metrics": file_df},
        args.out,
        args.format,
    )

    print(f"Analyzed {len(file_df)} files, {len(function_df)} functions under {target}")
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
    if args.post:
        endpoint = args.metrics_endpoint or (manifest.get("endpoints") or {}).get(
            "metrics", ""
        )
        rows = [
            _clean_record(record)
            for frame in (function_df, file_df)
            for record in frame.to_dict(orient="records")
        ]
        result = post_rows(rows, endpoint)
        if result.get("error"):
            print(
                f"warning: metrics run {run_id} saved locally but POST failed: "
                f"{result['error']}",
                file=sys.stderr,
            )
        else:
            print(
                f"metrics POST: {result.get('inserted', 0)} inserted, "
                f"{result.get('duplicates', 0)} duplicates"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
