# Static code metrics - implementation plan (as built)

**Status: ✅ implemented**; satisfies FR-INST-4
and the metrics leg of FR-INST-6. This document is the plan *and* the
as-built record - deviations from the original plan are marked **[revised]**.

## Context

The 9 static code metrics are specified in
`metrics/docs/static_code_metrics.md`. Four metrics are tree-sitter based
(parameter count, nesting depth penalty, average identifier length, variable
scope distance), four come from plain text or Radon (indentation variance,
line-width bounds, Halstead effort, comment ratio), and one - SonarQube
Cognitive Complexity - is queried from a local server and **stub-degradable**
(decision D5): without a reachable SonarQube it becomes NaN with a single
warning, never a failure.

## Layout (flat scripts, deliberately not a package)

```
metrics/
├── pyproject.toml            # uv workspace member; deps: radon, pandas,
│                             # requests, tree-sitter, tree-sitter-python
├── corpus/                   # deliberately imperfect sample files = default
│                             # analysis target (excluded from ruff)
├── docs/                     # this plan + static_code_metrics.md
├── src/
│   ├── main.py               # orchestrator
│   ├── parsers/
│   │   └── ts_parser.py      # the four tree-sitter metrics
│   └── analyzers/
│       ├── text_metrics.py   # indentation variance, line-width bounds
│       ├── radon_metrics.py  # Halstead effort, comment-to-code ratio
│       └── sonar_metrics.py  # stub-degradable SonarQube client (D5)
└── tests/
    └── test_static_metrics.py
```

**[revised]** Dependencies are managed by **uv** at the workspace root
(decision D16) - there is no `requirements.txt` and no per-package venv.
`metrics/test/` became `metrics/corpus/` in the repo restructure. A pytest
suite in `tests/` replaced manual-only verification.

## Module contracts

### `src/analyzers/text_metrics.py` - plain-text metrics (file-level)

- `get_indentation_variance(source: str) -> float`: population standard
  deviation (`statistics.pstdev`) of leading-whitespace width over non-blank
  lines, tabs expanded to 4 spaces, rounded to 2 decimals.
- `get_line_width_bounds(source: str) -> dict`:
  `{"max_line_width": int, "mean_line_width": float}`; blank lines excluded
  from the mean.

### `src/analyzers/radon_metrics.py` - Radon-based metrics

- `get_halstead_effort(source: str) -> dict`: via `radon.metrics.h_visit` →
  `{"total": float, "functions": {name: effort}}`. Syntactically invalid
  source returns zeros/empty rather than raising.
- `get_comment_ratio(source: str) -> float`: `radon.raw.analyze` →
  `(comments + multi) / sloc`, guarded for `sloc == 0`, rounded to 2
  decimals.

### `src/analyzers/sonar_metrics.py` - stub-degradable SonarQube client

- `get_cognitive_complexity(file_path, base_url="http://localhost:9000",
  token=None, timeout=1.5) -> float | None`: queries
  `/api/measures/component`; on any failure returns `None` (→ NaN/null in
  exports) and warns **once per process**, not per file.
- Follow-up to activate (documented in the module docstring): run
  `docker run -d -p 9000:9000 sonarqube:community`, scan the target with
  `sonar-scanner`, re-run the orchestrator.

### `src/parsers/ts_parser.py` - the four tree-sitter metrics

- The four metric functions keep their original signatures
  (`get_parameter_counts`, `get_nesting_penalty`,
  `get_average_identifier_length`, `get_variable_scope_distance`) and the
  `__main__` demo block still prints all four for `corpus/detect.py`.
- `collect_function_metrics(source_bytes: bytes) -> dict` runs all four and
  returns per-function rows (scope distance aggregated to max + mean; the
  per-variable dict stays available via the original function).
- **[revised - correctness fix]**
  The original plan said "keep the four existing metric functions
  untouched", but verification hand-counts caught a real bug: pairing the
  flat `captures()` lists with `zip()` misassigns names/values on files
  with methods or nested functions (tree-sitter returns each capture list
  in its own order). All three affected metrics now pair captures
  **per match** via `QueryCursor.matches()`. Duplicate function names in
  one file uniformly keep the **first** occurrence (known limitation,
  shared with the Halstead name-join in `main.py`).

### `src/main.py` - orchestrator

- CLI:
  `uv run python metrics/src/main.py [target_dir] [--out results/]
  [--sonar-url URL] [--format csv|jsonl] [--participant ID]
  [--condition COND] [--session ID] [--timestamp ISO]`;
  default target is `metrics/corpus/`.
- Discovers `*.py` recursively (skipping `venv/`, `__pycache__/`, etc.),
  reads each file once, fans out to all analyzers, and emits two tables:
  - `function_metrics`: one row per (file, function) - parameter_count,
    nesting_penalty, avg_identifier_length, max/mean scope distance,
    halstead_effort.
  - `file_metrics`: one row per file - indentation_variance, max/mean line
    width, comment_ratio, halstead_effort_total, cognitive_complexity (NaN
    while stubbed).
- **[framework additions]** Every row is stamped with the
  join keys `participantId`, `condition`, `sessionId`, a capture timestamp
  (`--timestamp`, else per-file mtime, ISO 8601 UTC), and `schemaVersion`
  (bump on any row-shape change, NFR-4) so metrics rows join the other legs
  on one timeline (FR-INST-6). `--format jsonl` mirrors the CSV rows as
  JSON Lines (NaN → `null`) for middleware ingestion.
- A prepared session should instead use `--manifest
  .phoenix/session-manifest.json`; the manifest supplies the assigned
  workspace, participant, condition, task, session, and metrics endpoint.
  `--post` mirrors rows after writing the local CSV/JSONL recovery files.
  Replays are idempotent on stable metric identity, and a missing SonarQube
  service is recorded as `sonarStatus=degraded` and
  `metricRunStatus=degraded-sonar` rather than hidden.

## Verification (all run green 2026-07-11)

1. `uv run pytest metrics` - analyzer unit tests, a regression test for the
   capture-pairing bug, and orchestrator end-to-end tests (join keys, JSONL
   null-degradation, bad-target exit code).
2. `uv run python metrics/src/parsers/ts_parser.py` - demo prints the four
   tree-sitter metrics for `corpus/detect.py`.
3. `uv run python metrics/src/main.py --participant P00 --condition
   unassisted` - writes both CSVs over `corpus/` (3 files, 11 functions)
   with join-key columns.
4. Spot-checks: parameter counts hand-verified against `corpus/` signatures
   (`flag_with_priority` = 4, `apply` = 3, `find_biggest_n` = 3); Halstead
   effort matches the `radon` CLI exactly (weather.py file total 5315.26;
   per-function 625.49 / 15.51 / 68.34); comment ratio matches a manual
   count on `plot_actual_util.py` (8 comment lines / 48 sloc → 0.17).
5. Sonar degradation: with no SonarQube up → exactly one warning,
   `cognitive_complexity` is NaN (CSV) / `null` (JSONL), exit code 0.

## Out of scope (documented follow-ups)

- Docker + SonarQube container deployment and scanner configuration
  (optional Docker profile, decision D5).
- Multi-language support beyond Python.
- Time-series runs over shadow-git workspace snapshots (agent leg
  provides the snapshotter; the orchestrator is already parameterized by
  target directory and timestamp).
