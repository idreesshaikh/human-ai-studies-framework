"""Tests for the metrics analyzers and the orchestrator (flat-script layout:
metrics/src is put on sys.path, per metrics/docs/implementation_plan.md)."""

import json
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import main as orchestrator  # noqa: E402
from analyzers.radon_metrics import (  # noqa: E402
    get_comment_ratio,
    get_halstead_effort,
)
from analyzers.text_metrics import (  # noqa: E402
    get_indentation_variance,
    get_line_width_bounds,
)
from parsers.ts_parser import collect_function_metrics  # noqa: E402

SAMPLE = textwrap.dedent(
    '''
    # module comment
    def outer(a, b, c):
        """Docstring."""
        total = 0
        for item in range(a):
            if item > b:
                total += item
        return total + c
    '''
)


def test_indentation_variance_of_flat_source_is_zero():
    assert get_indentation_variance("a = 1\nb = 2\n") == 0.0


def test_indentation_variance_known_value():
    # widths 0 and 4 -> population stdev 2.0; blank lines ignored
    assert get_indentation_variance("if x:\n    y = 1\n\n") == 2.0


def test_line_width_bounds():
    bounds = get_line_width_bounds("abcd\n\nab\n")
    assert bounds == {"max_line_width": 4, "mean_line_width": 3.0}


def test_comment_ratio():
    assert get_comment_ratio("# comment\nx = 1\n") == 1.0
    assert get_comment_ratio("") == 0.0


def test_comment_ratio_survives_syntax_errors():
    assert get_comment_ratio("def broken(:\n") == 0.0


def test_halstead_effort_per_function():
    report = get_halstead_effort(SAMPLE)
    assert report["total"] > 0
    assert report["functions"]["outer"] > 0


def test_halstead_effort_survives_syntax_errors():
    assert get_halstead_effort("def broken(:\n") == {"total": 0.0, "functions": {}}


def test_collect_function_metrics():
    rows = collect_function_metrics(SAMPLE.encode())
    row = rows["outer"]
    assert row["parameter_count"] == 3
    assert row["nesting_penalty"] == 3  # for at depth 0 (1) + if at depth 1 (2)
    assert row["avg_identifier_length"] > 0
    assert row["max_scope_distance"] >= row["mean_scope_distance"] >= 0


def test_parameter_counts_pair_correctly_across_nested_definitions():
    # Regression: pairing the flat captures() lists with zip() misaligned
    # names and parameter blocks on files with methods + nested functions.
    src = textwrap.dedent(
        """
        class A:
            def method(self, a, b=1):
                def callback(x):
                    return x
                return callback

        class B:
            def method(self, a, b, c):
                def callback(x, y):
                    return x + y
                return callback(1, 2)

        def solo():
            pass
        """
    )
    rows = collect_function_metrics(src.encode())
    assert rows["method"]["parameter_count"] == 3  # first occurrence (A.method)
    assert rows["callback"]["parameter_count"] == 1
    assert rows["solo"]["parameter_count"] == 0


def test_orchestrator_stamps_join_keys(tmp_path):
    (tmp_path / "sample.py").write_text(SAMPLE, "utf-8")
    join_keys = {
        "participantId": "P00",
        "condition": "unassisted",
        "sessionId": "S-test",
    }
    function_df, file_df = orchestrator.build_tables(
        tmp_path, join_keys, timestamp="2026-07-11T00:00:00+00:00"
    )
    for df in (function_df, file_df):
        assert len(df) == 1
        row = df.iloc[0]
        assert row["participantId"] == "P00"
        assert row["condition"] == "unassisted"
        assert row["sessionId"] == "S-test"
        assert row["timestamp"] == "2026-07-11T00:00:00+00:00"
        assert row["schemaVersion"] == orchestrator.SCHEMA_VERSION
    assert function_df.iloc[0]["function"] == "outer"
    assert function_df.iloc[0]["halstead_effort"] > 0


def test_orchestrator_jsonl_mirrors_rows_with_nan_as_null(tmp_path):
    (tmp_path / "sample.py").write_text(SAMPLE, "utf-8")
    exit_code = orchestrator.main(
        [
            str(tmp_path),
            "--out",
            str(tmp_path / "results"),
            "--format",
            "jsonl",
            "--participant",
            "P00",
            "--condition",
            "unassisted",
            "--session",
            "S-test",
        ]
    )
    assert exit_code == 0
    lines = (
        (tmp_path / "results" / "file_metrics.jsonl").read_text("utf-8").splitlines()
    )
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["participantId"] == "P00"
    assert record["cognitive_complexity"] is None  # sonar stub degraded
    assert record["schemaVersion"] == orchestrator.SCHEMA_VERSION


def test_orchestrator_rejects_missing_target(tmp_path, capsys):
    assert orchestrator.main([str(tmp_path / "nope")]) == 1
    assert "not a directory" in capsys.readouterr().err
