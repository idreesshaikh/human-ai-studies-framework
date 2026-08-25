"""
Tests for the metrics analyzers and the orchestrator (flat-script layout: metrics/src is
put on sys.path, per metrics/docs/implementation_plan.md).
"""

import json
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import main as orchestrator
from analyzers.radon_metrics import (
    get_comment_ratio,
    get_halstead_effort,
)
from analyzers.text_metrics import (
    get_indentation_variance,
    get_line_width_bounds,
)
from parsers.ts_parser import collect_function_metrics

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
    assert row["nesting_penalty"] == 3
    assert row["avg_identifier_length"] > 0
    assert row["max_scope_distance"] >= row["mean_scope_distance"] >= 0


def test_parameter_counts_pair_correctly_across_nested_definitions():
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
    assert rows["method"]["parameter_count"] == 3
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


@pytest.mark.parametrize("metric_set", ["parameter_count", ["parameter_count"]])
def test_orchestrator_can_select_a_metric_set(tmp_path, metric_set):
    (tmp_path / "sample.py").write_text(SAMPLE, "utf-8")

    function_df, file_df = orchestrator.build_tables(
        tmp_path,
        {"participantId": "P00", "condition": "unassisted", "sessionId": "S-test"},
        timestamp="2026-07-11T00:00:00+00:00",
        metric_set=metric_set,
    )

    assert "parameter_count" in function_df
    assert "halstead_effort" not in function_df
    assert "metricId" in file_df
    assert "cognitive_complexity" not in file_df


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
    assert record["cognitive_complexity"] is None
    assert record["schemaVersion"] == orchestrator.SCHEMA_VERSION


def test_orchestrator_rejects_missing_target(tmp_path, capsys):
    assert orchestrator.main([str(tmp_path / "nope")]) == 1
    assert "not a directory" in capsys.readouterr().err


def test_manifest_supplies_workspace_and_all_join_keys(tmp_path, capsys):
    (tmp_path / "sample.py").write_text(SAMPLE, "utf-8")
    manifest = tmp_path / "session-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "participantId": "P07",
                "condition": "unassisted",
                "sessionId": "s-kit",
                "taskId": "task-a",
                "runner": {"workspace": str(tmp_path)},
                "producers": {"metrics": {"metricSet": 42}},
            }
        ),
        "utf-8",
    )

    assert (
        orchestrator.main(
            [
                "--manifest",
                str(manifest),
                "--out",
                str(tmp_path / "results"),
                "--format",
                "jsonl",
            ]
        )
        == 0
    )
    record = json.loads(
        (tmp_path / "results" / "file_metrics.jsonl").read_text("utf-8").splitlines()[0]
    )
    assert record["source"] == "metrics"
    assert record["participantId"] == "P07"
    assert record["sessionId"] == "s-kit"
    assert record["taskId"] == "task-a"
    assert record["metricId"]
    assert "degraded-sonar" in capsys.readouterr().err


def test_manifest_errors_are_actionable(tmp_path):
    with pytest.raises(ValueError, match="could not read manifest"):
        orchestrator._load_manifest(tmp_path / "missing.json")

    invalid = tmp_path / "invalid.json"
    invalid.write_text("[]", "utf-8")
    with pytest.raises(ValueError, match="must be an object"):
        orchestrator._load_manifest(invalid)


def test_post_rows_handles_empty_and_missing_endpoint():
    assert orchestrator.post_rows([], "") == {
        "received": 0,
        "inserted": 0,
        "duplicates": 0,
        "error": None,
    }
    assert orchestrator.post_rows([{"metricId": "m"}], "")["error"] == (
        "no metrics endpoint"
    )


class _PostResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def test_post_rows_sends_json_and_returns_server_payload(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["request"] = request
        seen["timeout"] = timeout
        return _PostResponse({"received": 1, "inserted": 1, "duplicates": 0})

    monkeypatch.setattr(orchestrator.urllib.request, "urlopen", fake_urlopen)
    result = orchestrator.post_rows([{"metricId": "m"}], "https://example.test/metrics")

    assert result["inserted"] == 1
    assert seen["request"].method == "POST"
    assert seen["request"].get_header("Content-type") == "application/json"
    assert seen["timeout"] == 10.0


def test_post_rows_keeps_local_rows_when_server_is_unavailable(monkeypatch):
    def fake_urlopen(request, timeout):
        raise orchestrator.urllib.error.URLError("offline")

    monkeypatch.setattr(orchestrator.urllib.request, "urlopen", fake_urlopen)
    result = orchestrator.post_rows([{"metricId": "m"}], "https://example.test/metrics")

    assert result["received"] == 1
    assert result["inserted"] == 0
    assert "offline" in result["error"]


def test_clean_record_converts_missing_values_to_json_null():
    cleaned = orchestrator._clean_record({"metricId": "m", "value": float("nan")})

    assert cleaned == {"metricId": "m", "value": None}


def test_main_posts_manifest_rows_after_writing_them(tmp_path, monkeypatch, capsys):
    (tmp_path / "sample.py").write_text(SAMPLE, "utf-8")
    monkeypatch.setattr(
        orchestrator,
        "post_rows",
        lambda rows, endpoint: {
            "received": len(rows),
            "inserted": len(rows),
            "duplicates": 0,
            "error": None,
        },
    )

    assert (
        orchestrator.main(
            [
                str(tmp_path),
                "--out",
                str(tmp_path / "results"),
                "--post",
                "--metrics-endpoint",
                "https://example.test/metrics",
            ]
        )
        == 0
    )
    assert "metrics POST:" in capsys.readouterr().out


def test_metrics_post_rejects_non_http_endpoint():
    result = orchestrator.post_rows([{"metricId": "m"}], "file:///tmp/metrics")

    assert result["error"] == "metrics endpoint must use http or https"
