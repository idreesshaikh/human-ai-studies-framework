# Phase 04 — Static-metrics leg

> Read first: `metrics/docs/static_code_metrics.md`, `metrics/docs/implementation_plan.md`.
> **Satisfies:** FR-INST-4, FR-INST-6. **Status:** ✅ built.

## The idea

One of the four data legs: 9 static code metrics over a directory of
code, each capturing a complexity or readability dimension. It
fans a session's files into `function_metrics` / `file_metrics` rows, every row
stamped with the join keys so it lands on the one timeline.

## What it builds

`metrics/` (flat `src/` scripts — deliberately not a package):
- `src/parsers/ts_parser.py` — tree-sitter parsing.
- `src/analyzers/{radon_metrics,sonar_metrics,text_metrics}.py` — the nine
  metrics: nesting-depth penalty (exponential), cognitive complexity (SonarQube
  API, stub-degradable), parameter count (Miller's Law), Halstead effort
  (Radon), variable scope distance, indentation variance, line-width bounds,
  average identifier length, comment-to-code ratio.
- `src/main.py` — the orchestrator, emitting JSONL for middleware ingest.
- `corpus/` — deliberately-imperfect sample targets (ruff-excluded).

Run: `uv run python metrics/src/main.py <dir> --participant P1 --format jsonl`.

## Acceptance

- All 9 metrics compute per-function and per-file as applicable (FR-INST-4).
- Every row carries `participantId`, `condition`, `sessionId`, timestamp, and a
  schema version (FR-INST-6).
- Cognitive complexity stub-degrades to NaN with one warning when SonarQube is
  absent (D5).

## Verification

- `uv run pytest metrics` (coverage-gated); metric-to-construct mapping matches
  the matrix doc.
