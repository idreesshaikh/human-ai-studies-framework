# Phase 08: Analysis recipes & honest statistics

> Read first: `requirements/srs.md` §FR-ANA, `analysis/` package.
> **Satisfies:** FR-ANA-1..4, NFR-6, NFR-8. **Status:** ✅ built.

## The idea

Analyses are **recipes**: pluggable modules declaring `id`, `answers` (RQ ids),
`requires` (data elements), and a `run` that emits tables, figures, and methods
text. A runner executes the protocol's analysis plan and emits a per-RQ report.
Two disciplines are enforced by construction: `requires` is validated *before*
data collection ends (design defects caught early), and every statistical line
carries an exact test, effect size, and per-cell n: a bare p-value is
impossible to emit (NFR-8).

## What it builds

`analysis/` (Python package, CLI `analysis`):
- `core.py`: the recipe contract + registry.
- `runner.py` + `report.py`: execute the plan, emit the per-RQ report.
- `dataset.py`: pull the joined one-timeline dataset from the middleware.
- `stats.py`: the honesty layer (exact tests, effect sizes, per-cell n,
  small-n framing).
- `recipes/`: the built-in set: `fatigue-by-condition`, `stuck-episodes`,
  `tlx-debrief`, `paste-behavior`, `code-quality-by-condition`,
  `ai-review-behavior`, `agent-interaction-dynamics`,
  `task-outcome-by-condition`.

CLI: `analysis run | validate | paper | retrospective | list`.

## Acceptance

- `analysis validate` fails loudly on missing data elements before collection
  ends (FR-ANA-2); the report is organized by RQ (FR-ANA-4).
- Recipes are deterministic given a dataset (seeded jitter, no wall-clock in
  outputs), per NFR-6.

## Verification

- `uv run pytest analysis`; a report regenerates bit-stably modulo timestamps.
