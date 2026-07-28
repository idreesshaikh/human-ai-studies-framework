# Phase 23 — The Session Timeline

> Self-contained: execute this file in a fresh session at the repo root.
> Read first: `docs/VISION.md`, `docs/roadmap/README.md` (walls #4/#8/#10),
> `docs/roadmap/03-ingestion-middleware.md` (the `/sessions/{id}/events` and
> `/studies/{id}/live` routes this phase reads, already built — no new
> backend endpoint needed), `requirements/build-vs-adopt.md`'s D17/D19
> entries (stale — see the note below, read anyway for the original
> rationale), the `dataviz` skill (this repo's actual current charting
> convention, superseding D17's Svelte-era framing).

**Depends on:** Phase 03 (ingestion middleware — `GET /sessions/{id}/events`,
already returns full per-event rows with `ts`, `type`, `source`, `seq`,
`flags`), Phase 14 (study workspace shell, `platform/src/components/charts/DataTab.tsx`),
Phase 19 (`/studies/{id}/live` — per-session rate buckets + gap facts,
already built and consumed by `EnrollmentPanel`'s streaming-status check).
**Satisfies:** FR-DASH-4.
**Elicited:** owner requirement (`requirements/srs.md`, Must) — "the
one-timeline invariant made visible" — discovered unphased 2026-07-21
while auditing the roadmap; formalized as its own phase rather than folded
into Phase 14 (where FR-DASH-4 is currently 🔶) since the swimlane itself
was never scheduled as concrete slices anywhere.
**Status:** ✅ built. See the deviations log below.

## The idea

Wall #4 says every row of every leg carries the same join keys onto "one
timeline" — but nothing in the platform actually **shows** that timeline.
`DataTab.tsx` today renders per-session integrity cards (event count, gap
count, flags) and a metric-distribution strip (`MetricStrip.tsx`,
FR-DASH-5, already ✅) — useful summaries, but neither answers "what
happened, in what order, across all four legs, in this one session?" This
phase builds that swimlane: one time axis, one lane per leg (cognitive,
behavioral, static-metrics, agent-interaction), each event a mark
positioned by `ts`, colored/shaped by type — the one-timeline invariant
made literally visible, using data every leg already emits and an endpoint
(`/sessions/{id}/events`) already built. This is purely a rendering phase;
no new backend contract, no new privacy surface, no new join key.

**A note on the stale build-vs-adopt entries:** `requirements/build-vs-adopt.md`'s
D17 ("LayerChart vs hand-rolled SVG + d3-scale") and D19 (Vitest) both
predate the platform's React rebuild (D34/D37) and speak in Svelte terms
("Svelte renders SVG natively"). Checked directly: the current
`MetricStrip.tsx` (the one shipped chart) uses **no d3-scale dependency at
all** (`platform/package.json` confirmed clean of it) — the hand-rolled
mark-and-scale approach survived the framework migration, the specific
d3-scale adoption did not. This phase follows `MetricStrip.tsx`'s actual
current pattern (hand-rolled SVG, no new charting dependency) rather than
resurrecting D17's d3-scale line item; if a scale library turns out to be
genuinely needed, that's a fresh `build-vs-adopt` row against the current
stack, not a resurrection of a Svelte-era decision (NFR-10).

Non-negotiable bounds, inherited verbatim:

- **Wall #4, made visible, not reinterpreted.** The swimlane renders
  exactly the join-keyed rows every leg already emits; it invents no new
  event shape.
- **Wall #8, honest statistics.** No animation on data (this repo's
  standing rule — "statistics never animate"); a swimlane is a factual
  record, not a reveal.
- **Wall #10, NFR-12.** A chart-only view fails keyboard/screen-reader
  users — this phase ships a table-view twin from day one, not as a
  follow-up.
- **No new dependency** (NFR-10) unless a fresh, current-stack
  build-vs-adopt row justifies one.

## §0 — Traceability spine — do this first

1. **No new SRS/traceability rows needed** — FR-DASH-4 already has both
   (`requirements/srs.md:87`, `requirements/traceability.md:52`), currently
   🔶 "session status integrity shown; the swimlane view is not yet
   built." This phase's verification flips that row to ✅ (golden rule 3);
   do not re-add or renumber it.
2. **No glossary terms needed** — "swimlane timeline," "lane," "mark" are
   plain English in this context, not glossary-governed terms
   (`participant`/`condition`/`recipe` etc. remain the golden-rule-4 terms
   already in use).
3. **Tracker row:** this phase already has its own "The session timeline
   (23)" heading + row in `docs/roadmap/README.md` (added alongside this
   spec) — flip its status only once verification passes.

## Slices

### Slice A — The lane-assembly module (pure, testable)

`platform/src/lib/timeline.ts` (new). No backend change — reads existing
`GET /sessions/{id}/events` responses.

1. **`assembleLanes(events: EventRow[]): Lane[]`** — groups events by
   `source` (`tern`, `agent-capture`, `workspace-snapshot`,
   `task-harness`, `agent-derived`, static-metrics rows if present),
   sorted by `ts` within each lane. Deterministic: same input → byte-
   identical lane assignment and ordering (mirrors the design-conversation
   compiler's own "replay is deterministic" standard, applied here to
   layout rather than compilation).
2. **`timeScale(events, width): (ts: string) => number`** — a minimal
   linear time-to-pixel mapping (hand-rolled, matching `MetricStrip.tsx`'s
   existing no-dependency pattern; see the stale-D17 note above). Handles
   the empty/single-event edge case without dividing by zero.
3. **Tests:** checked directly — D19's "Vitest" adoption never happened
   either; `platform/package.json` has no test script and no `.test.ts`
   file exists anywhere under `platform/`. The platform's actual current
   verification pattern is the bespoke `scripts/verify-*.mjs` demo-script
   convention (`verify-slice1.mjs`, `verify-shell.mjs`, etc., run by
   `npm run check`'s `verify` step) — add `scripts/verify-timeline.mjs`
   following that exact pattern (a standalone script asserting lane
   assignment is deterministic and replayable, every event lands inside
   `[0, width]`, a single-event session doesn't crash the scale function,
   and gap facts — `gapCount`/`missingEvents`, already computed
   server-side by `_session_gap_facts` — surface as a visibly distinct
   mark rather than silently dropped), and wire it into `package.json`'s
   `verify` script alongside the other four. Do not introduce Vitest for
   this alone (NFR-10) — match the house convention.

### Slice B — The swimlane marks + table-view twin

`platform/src/components/charts/SwimlaneTimeline.tsx` (new).

1. SVG marks: thin ticks/bars per event, one row per lane, a hairline grid
   for the time axis — this repo's established `dataviz` skill conventions
   (thin marks, validated palette, both-theme support), not a
   from-scratch visual language.
2. A synchronized **table view** (event | lane | type | ts | flags) toggled
   the same way `MetricStrip.tsx` already toggles chart/table
   (`ChartScatter`/`Table2` icon pattern, reused verbatim for consistency
   rather than inventing a second toggle affordance).
3. Flag/gap marks render distinctly (e.g. the `unauthenticated`/
   `credential-mismatch` flags Phase 19 introduced, and `seq`-gap facts)
   so a researcher can literally see where the timeline's integrity is
   uncertain — this is FR-DASH-4's "made visible" promise extended to
   Phase 19's own new flag vocabulary.

### Slice C — Wire into `DataTab`

1. `DataTab.tsx` gains a per-session drill-in: clicking a session card
   (already rendered today) expands or navigates to
   `<SwimlaneTimeline sessionId={s.sessionId} />`, fetching
   `GET /sessions/{id}/events` directly — no new endpoint, no change to
   `middleware/`.
2. NFR-12: both-theme + reduced-motion screenshots of the swimlane and its
   table-view twin; axe clean; keyboard-complete drill-in → table-view
   toggle → back.

## Degrees of freedom

- **Drill-in mechanics** — inline expansion vs. a route to
  `/study/:id/sessions/:sid` (D18's existing route shape already reserves
  this exact path); either, whichever the current router setup makes
  cheaper.
- **Lane ordering/coloring** — the four legs' visual order and the palette
  mapping are the builder's call within the `dataviz` skill's validated
  palette, not fixed by this spec.
- **Whether static-metrics rows get their own lane or a summary marker** —
  static metrics are per-commit, not per-timestamp-event in the same sense
  as the other three legs; decide based on what's actually useful once
  real multi-leg session data is on screen, and log the choice.

## Acceptance (maps to fit criteria)

- FR-DASH-4: a per-session swimlane renders events from all legs present
  in that session on one time axis, byte-identical lane assignment on
  replay of the same event set; a table-view twin carries the same data
  losslessly; gap/flag facts are visually distinct, not merged away.
- NFR-8: no statistic in this view animates or reveals progressively; it
  renders complete on load.
- NFR-12: both-theme, reduced-motion, axe-clean, keyboard-complete.

## Verification steps

1. `platform/`: `npm run check` green (`tsc -b && lint && verify && build`),
   including the new `scripts/verify-timeline.mjs`.
2. Manual walkthrough: open a session with events from at least two legs
   (the existing `middleware/scripts/replay_session.py` demo seed already
   posts a cognitive + behavioral session — reuse it rather than
   fabricating new fixture data) → confirm the swimlane renders both legs
   correctly ordered → toggle to table view → confirm the same rows,
   losslessly.
3. NFR-12 evidence archived for the swimlane + table-view states, both
   themes + reduced-motion.
4. Confirm FR-DASH-4's traceability row (🔶 → ✅) and this phase's tracker
   row are flipped only after 1–3 are green (golden rule 3).

## Deviations log

Record departures here and in `requirements/traceability.md` §3 as they
occur — in particular, whether a scale-library dependency was genuinely
needed (with a fresh build-vs-adopt row if so) or the hand-rolled approach
held.
