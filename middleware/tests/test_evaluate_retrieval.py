"""A synthetic three-paper benchmark verifies the runner's contract."""

import importlib.util
import json
from pathlib import Path

import pytest
from middleware.db import CORPUS_STUDY_ID, Paper, make_session_factory

from middleware import paper_index

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "retrieval_runner", ROOT / "scripts/evaluate_retrieval.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
corpus_digest, evaluate = runner.corpus_digest, runner.evaluate


@pytest.fixture
def benchmark(tmp_path):
    database = tmp_path / "benchmark.sqlite3"
    factory = make_session_factory(f"sqlite:///{database}")
    with factory() as session:
        for ref, title in [
            ("corpus:a", "Coding assistant task completion time"),
            ("corpus:b", "Mental demand and programming workload"),
            ("corpus:c", "Unrelated deployment logging"),
        ]:
            session.add(
                Paper(
                    study_id=CORPUS_STUDY_ID,
                    paper_ref=ref,
                    title=title,
                    year=2026,
                    tier="B",
                    source="fixture",
                    added_at="2026-10-08T12:00:00Z",
                )
            )
            paper_index.index_paper(session, ref, title, title)
        session.commit()
        digest = corpus_digest(session)
    payload = {
        "version": "1",
        "corpusDigest": digest,
        "labelProvenance": "human-adjudicated",
        "reviewers": ["fixture-reviewer-a", "fixture-reviewer-b"],
        "cases": [
            {
                "id": "q1",
                "split": "test",
                "query": "task completion time",
                "grades": {"corpus:a": 2},
            },
            {
                "id": "q2",
                "split": "test",
                "query": "mental demand",
                "grades": {"corpus:b": 2},
            },
        ],
    }
    path = tmp_path / "benchmark.json"
    path.write_text(json.dumps(payload))
    return database, path, payload


def test_metrics_and_latencies_match_the_synthetic_benchmark(benchmark):
    database, path, _ = benchmark
    result = evaluate(path, database)
    assert result["cases"] == 2
    assert result["metrics"] == {
        "recall@5": 1.0,
        "recall@10": 1.0,
        "MRR": 1.0,
        "nDCG@10": 1.0,
    }
    assert 0 <= result["latencyMs"]["p50"] <= result["latencyMs"]["p95"]


@pytest.mark.parametrize("change", ["reviewers", "duplicate", "digest"])
def test_unreviewed_or_changed_benchmarks_are_refused(benchmark, change):
    database, path, payload = benchmark
    if change == "reviewers":
        payload["reviewers"] = ["one-reviewer"]
    elif change == "duplicate":
        payload["cases"][1]["id"] = "q1"
    else:
        payload["corpusDigest"] = "stale"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        evaluate(path, database)
