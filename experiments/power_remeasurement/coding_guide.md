# Extraction and coding

Include English empirical studies posted or published from 2022-01-01 through
2026-10-01 with human programmers/developers, an AI coding assistant or LLM-based
tool, and a quantitative outcome. Exclude model-only benchmarks, qualitative-only
reports, tutorials, position papers, and duplicate analyses of one dataset.
Screening decisions are `include`, `exclude`, or `pending`; every decision records
a reason and coder. Resolve duplicate datasets before extraction.

Extract from full text only. `abstract_only` is `true` or `false`; abstract-only
rows never enter indicators. Leave unknown numeric values blank. Every full-text
row requires a coder and a page/table reference. Preserve both coders' original
files; record adjudication separately rather than overwriting either file.

- `design`: between, within, crossover, single-arm, observational, other.
- `participants`: students, professionals, mixed, crowd, not_stated.
- `primary_outcome_type`: time, correctness, rating, count, other.
- Reporting fields: yes/no; power and preregistration also allow not_stated;
  correction also allows not_applicable and not_stated; tool/version allows partial.
- Sample sizes and task/comparison counts: positive integers or blank; n_per_arm
  is extracted only when explicitly stated, never inferred by dividing total n.
- Citation, outcome, effect type, source reference and coder are free text.
  Effect value is the paper's stated estimate, never used to compute sensitivity.

`n_primary_comparisons` is an explicit addition to the plan's extraction columns:
it is needed to identify the denominator for multiple-comparison correction.
Do not infer this eligibility from whether a correction was reported.

Double-code a deterministic random 20% (at least 15 studies; seed 20261008), then
report Cohen's kappa per categorical field and raw agreement for numeric values.
Exclude fields with kappa below 0.6 from conclusions. No independent second coder
has been assigned yet, so reliability and research conclusions remain pending.

Run `uv run --package analysis python experiments/power_remeasurement/indicators.py`
after extraction. It joins screening decisions, reports every missing denominator,
and uses exact binomial intervals. Sensitivity uses assumed design-level d,
alpha 0.05 and 80% power; it excludes crossover/observational designs.
