"""Evaluate the local retrieval ladder against an independently judged corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import statistics
import time
from pathlib import Path

from middleware.db import CORPUS_STUDY_ID, Paper
from middleware.retrieval_metrics import mean, ndcg_at_k, recall_at_k, reciprocal_rank
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from middleware import matching


def corpus_digest(session: Session) -> str:
    rows = sorted(
        session.execute(
            select(Paper.paper_ref, Paper.title, Paper.year).where(
                Paper.study_id == CORPUS_STUDY_ID
            )
        ).tuples()
    )
    canonical = json.dumps([list(row) for row in rows], separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def evaluate(benchmark: Path, database: Path) -> dict:
    document = json.loads(benchmark.read_text())
    if document.get("labelProvenance") != "human-adjudicated":
        raise ValueError("benchmark labels must be human-adjudicated")
    if len(set(document.get("reviewers", []))) < 2:
        raise ValueError("benchmark requires two distinct reviewers")
    cases = document.get("cases", [])
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("benchmark case ids must be unique")
    cases = [case for case in cases if case["split"] == "test"]
    if not cases:
        raise ValueError("benchmark has no test cases")
    uri = database.resolve().as_uri() + "?mode=ro"
    engine = create_engine("sqlite://", creator=lambda: sqlite3.connect(uri, uri=True))
    metrics = {name: [] for name in ("recall@5", "recall@10", "MRR", "nDCG@10")}
    latencies = []
    try:
        with Session(engine) as session:
            digest = corpus_digest(session)
            if document.get("corpusDigest") != digest:
                raise ValueError("corpus digest differs from the judged snapshot")
            for case in cases:
                grades = case["grades"]
                if any(
                    type(grade) is not int or grade not in (0, 1, 2)
                    for grade in grades.values()
                ):
                    raise ValueError("relevance grades must be integers from 0 to 2")
                start = time.perf_counter()
                results = matching.match_papers(
                    session, case["query"], limit=10, use_llm=False, expand=False
                )
                latencies.append((time.perf_counter() - start) * 1000)
                ranked = [row["ref"] for row in results]
                relevant = {ref for ref, grade in grades.items() if grade > 0}
                metrics["recall@5"].append(recall_at_k(ranked, relevant, 5))
                metrics["recall@10"].append(recall_at_k(ranked, relevant, 10))
                metrics["MRR"].append(reciprocal_rank(ranked, relevant))
                metrics["nDCG@10"].append(ndcg_at_k(ranked, grades, 10))
    finally:
        engine.dispose()
    p95 = (
        statistics.quantiles(latencies, n=100, method="inclusive")[94]
        if len(latencies) > 1
        else latencies[0]
    )
    return {
        "corpusDigest": digest,
        "cases": len(cases),
        "metrics": {name: mean(values) for name, values in metrics.items()},
        "latencyMs": {"p50": statistics.median(latencies), "p95": p95},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", required=True, type=Path)
    parser.add_argument("--db", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.benchmark, args.db), indent=2))
