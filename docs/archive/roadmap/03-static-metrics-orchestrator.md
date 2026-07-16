# Mega-Prompt 03 - Static Metrics Orchestrator

> Self-contained: execute this file in a fresh working session at the repo
> root. Read `docs/archive/roadmap/00-VISION.md` first.

**Depends on:** nothing (parallel-safe with 01/02)
**Status:** ✅ Done (2026-07-11)

## Context

The metric set, toolchain, and rationale are specified in
`metrics/docs/static_code_metrics.md` - the 9-metric cognitive-load matrix
(structural/control-flow, working-memory/volume, visual/semantic-friction
groups, each metric tied to a construct like Miller's Law) with the
tree-sitter + Radon + SonarQube toolchain. That doc's three milestones are
compressed into this single phase (SonarQube stays the degradable Docker
profile per decision D5). A detailed implementation plan already exists at
`metrics/docs/implementation_plan.md` - follow it, with two updates from the
repo restructure: the code root is `metrics/` (flat script layout:
`src/parsers/ts_parser.py`, `src/analyzers/`, `src/main.py`, `test/`), and
dependencies are managed by **uv, not requirements.txt** - add radon and
pandas with `uv add --package metrics radon pandas` (requests only if the
sonar stub needs it) and run everything via `uv run` from the workspace.

Four tree-sitter metrics exist (parameter count, nesting penalty, average
identifier length, variable scope distance - per-variable, printed
individually). The plan adds five more (indentation variance, line-width
bounds, Halstead effort, comment ratio, stubbed SonarQube cognitive
complexity) and an orchestrator emitting `function_metrics.csv` +
`file_metrics.csv`.

## RE traceability

Satisfies FR-INST-4 (the 9-metric matrix) and the metrics leg of FR-INST-6
(join keys on every row). Rows flipped in `requirements/traceability.md` on
completion (2026-07-11).

## Objective

Execute `metrics/docs/implementation_plan.md` in full, with these framework
additions on top:

1. **Join keys** - the orchestrator must accept `--participant`,
   `--condition`, `--session` and stamp every CSV row with them (plus a
   capture timestamp passed in or derived from file mtime), so metrics rows
   join the Cognitive Overlay timeline. This is the framework's one-timeline
   invariant; do not skip it.
2. **Machine-readable output option** - `--format jsonl` mirroring the CSV
   rows as JSON Lines, one row per record, matching the extension's
   convention (future middleware ingestion, Mega-Prompt 04).

## Acceptance criteria

- All items in the plan's own Verification section pass (demo still runs,
  orchestrator produces both CSVs over the test corpus, spot-checks match
  `radon` CLI, sonar stub degrades to NaN with a single warning).
- CSV/JSONL rows carry participant/condition/session/timestamp columns.

## Verification

- Run the plan's verification steps; additionally run with
  `--participant P00 --condition unassisted` and confirm the columns.
  Update `docs/archive/roadmap/00-VISION.md` tracker and `requirements/traceability.md`.
