# Retrieval benchmark

The benchmark is a human-adjudicated judgment file held outside git until reviewed.
It freezes a particular corpus and separates calibration from test queries. No
human benchmark or retrieval baseline has been collected yet.

```json
{
  "version": "1",
  "corpusDigest": "SHA256_OF_THE_JUDGED_CORPUS",
  "labelProvenance": "human-adjudicated",
  "reviewers": ["reviewer-a", "reviewer-b"],
  "cases": [
    {
      "id": "q001",
      "split": "test",
      "query": "Methods for comparing developer task completion time",
      "grades": {"arxiv:example": 2, "corpus:example": 1}
    }
  ]
}
```

This example illustrates the format; its placeholders are not judgments. Require
at least 50 cases and two distinct reviewers. Grade title and abstract only:
2 directly answers the query, 1 supplies relevant background, and 0 or absent is
irrelevant. Use one query per intent, without copying a paper's title. Keep the
two raw judgment sheets and record disagreements and adjudication separately.
For a doubly judged subset, compute Cohen's kappa on relevant versus irrelevant;
the proposed minimum is 0.6, subject to owner approval.

The digest is SHA-256 of UTF-8 JSON for the sorted `(paper_ref, title, year)` triples
of every `platform-corpus` row, serialized as arrays with `separators=(",", ":")` and
Python's default `ensure_ascii=True`. `scripts/evaluate_retrieval.py:corpus_digest`
defines the serialization. A changed title, year, or accepted paper invalidates
the judgment snapshot; refreshed papers need separate judgments.

```bash
uv run python scripts/evaluate_retrieval.py --benchmark /path/to/reviewed.json --db /path/to/corpus.sqlite3
```

The runner opens SQLite read-only, verifies provenance, reviewers, unique case ids,
grade values, and the corpus digest, and evaluates only test cases. It calls the
current retrieval ladder with LLM reranking and remote expansion disabled and
reports recall@5, recall@10, MRR, nDCG@10 and p50/p95 latency in milliseconds.
Undefined metrics are omitted from their means. The runner's small synthetic tests
verify the machinery; they are not an empirical retrieval baseline.

Record the reviewed benchmark, agreement report, corpus digest, baseline output,
and latency budget before considering dense retrieval. Dense retrieval remains
gated on that baseline; no embedding dependencies or model weights were added.
