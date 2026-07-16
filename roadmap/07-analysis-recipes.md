# Mega-Prompt 07 - Analysis Recipes

> Self-contained: execute this file in a fresh working session at the repo
> root. Read `roadmap/00-VISION.md`, `requirements/srs.md`, and the middleware
> dataset endpoint docs first.

**Depends on:** 03 (metrics), 04 (middleware dataset export)
**Status:** ✅ Done (2026-07-12) - see the MP-07 row in
`requirements/traceability.md` (FR-ANA-1–4 ✅, FR-ANA-5 🔶 until MP-09's
second paper recipe; deviations noted there)

## Context

"We don't build everything from scratch" becomes architecture here: an
**analysis recipe** is a pluggable Python module that consumes the unified
dataset and emits tables + figures + a methods paragraph. Published paper
algorithms become recipes later; for the vertical slice we implement the
recipes our pilot's analysis plan (in the protocol YAML) declares. RE thread:
the protocol's analysis plan maps RQ → recipe, so results are traceable to
requirements by construction.

## RE traceability

Satisfies FR-ANA-1, FR-ANA-2, FR-ANA-3, FR-ANA-4 (FR-ANA-5 with MP-09),
NFR-8, and NFR-6 (with MP-09); update `requirements/traceability.md` on
completion.

## Deliverables

1. **Recipe contract** (`analysis/core.py`): a recipe declares `id`,
   `answers` (RQ ids), `requires` (event types / metric columns), and
   implements `run(dataset) -> RecipeResult` (tables as DataFrames, figures
   as matplotlib Figures, a plain-language summary, and the exact statistical
   procedure text for the methods section). A registry discovers recipes;
   `requires` is checked against the dataset before running - a recipe
   whose data is missing fails loudly at plan-validation time, not at
   analysis time.
2. **Built-in recipes** (each with its statistical test chosen and justified
   in the docstring - these are small, deliberately):
   - `fatigue-by-condition` - Likert trajectories, within-subject comparison
     (Wilcoxon signed-rank for paired; Mann-Whitney U for between).
   - `stuck-episodes` - frequency/duration of stuck prompts by condition.
   - `paste-behavior` - paste size/frequency distributions by condition
     (needs Mega-Prompt 05 data).
   - `code-quality-by-condition` - static-metrics comparison with effect
     sizes (Cliff's delta), not just p-values.
   - `tlx-debrief` - end-survey subscale comparison.
   - `ai-review-behavior` - RQ-P4: review latency per `ai_suggestion`
     (accept vs. reject), scroll coverage of AI-origin bursts before
     save/accept (join `visible_range` against burst line ranges), accept
     rate by suggestion size quartile, and review latency vs. most recent
     fatigue response on the shared timeline. This is the differentiator
     recipe - no off-the-shelf tool computes it.
   - `agent-interaction-dynamics` - RQ-P5: turn cadence and prompt/response
     size distributions, tool-call mix, reliance-loop frequency/duration,
     time-share of conversation vs. coding (against active-time
     denominators), and their co-variation with fatigue and stuck episodes.
   - `task-outcome-by-condition` - RQ-P1–P5's ground truth: acceptance-test
     pass rates, time-to-first-green, and outcome-conditioned splits of the
     other recipes' headline measures (needs MP-12's task harness).
3. **Runner CLI**: `analysis run <protocol.yaml> --study <id>` - executes
   every recipe the protocol's analysis plan names, writes
   `results/<study>/<recipe>/` (CSVs, PNGs/SVGs, `summary.md`), and a
   top-level `report.md` stitching summaries per RQ.
4. **One replication demo**: implement one metric/algorithm from a published
   developer-study paper as a recipe (cite it in the docstring) - the
   proof-of-concept for "papers become recipes".
5. pytest: contract validation, one recipe end-to-end on a synthetic dataset
   fixture with a known answer.

## Implementation guidance

- pandas + scipy + matplotlib; follow the project's data-viz conventions
  (consistent palette, labeled axes, honest scales) in all figure code.
- Small-n honesty: report exact tests, effect sizes, and n per cell; never
  bare p-values. The pilot will be tiny - the recipes must not oversell.

## Acceptance criteria

- `analysis run` over a seeded study produces a `report.md` where every
  section names the RQ it answers; a recipe with missing requirements fails
  at validation with a message naming the missing event type.

## Verification

- pytest green; full run against replayed pilot data; open the figures.
  Update `roadmap/00-VISION.md` tracker and `requirements/traceability.md`.
