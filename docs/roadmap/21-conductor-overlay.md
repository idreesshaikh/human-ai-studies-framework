# Phase 21 — The Conductor Overlay (study conductor, part 3 of 3)

> Self-contained: execute this file in a fresh session at the repo root.
> Read first: `docs/VISION.md`, `docs/roadmap/README.md` (the walls +
> autonomy charter), `docs/roadmap/07-agent-interaction-leg.md` (edit-burst
> origin classification this phase joins against), `docs/roadmap/05-cognitive-leg.md`
> (the fatigue/stuck prompt patterns this phase's UI mirrors),
> `docs/roadmap/20-capture-console.md` (the sequencing note below —
> read its Slice A before assuming this phase's probe config ships through
> the same toggle console), `extension/PROJECT_GUIDE.md`.

**Depends on:** Phase 07 (`extension/src/core/behavior.ts`'s `EditBurst`/
`EditOrigin` classification — an accepted chunk is an `origin: 'ai'` burst
the participant keeps), Phase 05 (`extension/src/core/surveys.ts`'s
`LikertItem` pattern, `stuckPrompt.ts`'s inline CodeLens-prompt UI as the
adapter pattern to mirror), Phase 19 (capture config derivation,
session-boundary application discipline).
**Satisfies:** FR-INST-19 (comprehension probes), FR-DASH-12 (probe-bank/
cadence protocol config, new).
**Elicited:** implied by Phase 19's own scope note — "Phase 21 ('the
conductor overlay') enriches the in-editor participant experience" —
formalized 2026-07-21 while auditing the roadmap for unspecced phases.
**Status:** Specced (2026-07-21). Not built.

## The idea

The engagement → comprehension → maintenance chain (RQ-C1–C4) is
unmeasurable today: the cognitive leg captures fatigue and stuck episodes,
the agent leg captures turns, but nothing joins "the participant accepted
an AI-produced chunk" to "did they understand what they accepted." Phase
21 closes that gap inside the *existing* TERN extension — no
new extension, no new UI paradigm. When an edit burst closes with
`origin: 'ai'` and the participant doesn't immediately undo it (an
**accepted chunk**, per the glossary term FR-INST-19 already reserved), a
short, timeboxed **comprehension probe** — predict-output or locate-change,
protocol-configured — appears using the same inline CodeLens pattern
`stuckPrompt.ts` already proved: no modal, no focus steal, quietly expires
if ignored. The response carries a **chunk reference** joining it back to
the edit burst / agent turn that produced the chunk, never the code itself
(FR-ETH-2: metadata and shapes only).

This is **part 3 of the study-conductor arc**, and the one genuinely new
in-editor surface of the three (19 and 20 are config/control; 21 is the
first participant-facing addition since the original fatigue/stuck
instruments). "Conductor overlay" names the destination the arc was always
aimed at — VISION.md's adopting-researcher journey ends at "data (live
sessions)"; this phase is what a participant's *editor* looks like once
that data collection is actually running.

Non-negotiable bounds, inherited verbatim:

- **NFR-1, fire-and-forget.** A probe never blocks the participant; an
  ignored probe times out exactly like a stuck prompt, recorded as
  `expired`, never as a forced answer.
- **Wall #6.** Probe cadence/config (which probe types, how often) is
  read at session start only — no mid-session reconfiguration. If Phase 20
  ships first, this reuses its toggle console; if not (see dependency
  note), FR-DASH-12's config still applies only at the session boundary.
- **FR-ETH-2, privacy by construction.** A probe's prompt is built from
  chunk *metadata* (line count, language, which edit burst) — never the
  code text itself. The response records correctness/timing, never
  reproduces the snippet.
- **`src/core` never imports `vscode`** (NFR-3). The probe state machine
  and probe-bank content generators are pure; only the CodeLens rendering
  touches VS Code APIs.
- **Schema versioning** (NFR-4). This is a genuinely new event shape — bump
  `SCHEMA_VERSION` (currently `3`, `extension/src/core/types.ts`) to `4`.

**Sequencing note (resolve before coding):** Phase 20 is where a metric's
on/off state becomes researcher-toggleable; a comprehension probe is
itself "a togglable metric" in spirit. Two honest options: (a) sequence
this phase strictly after Phase 20 lands, so probe cadence is toggleable
from day one through the Slice A.2 endpoint Phase 20 built; or (b) ship
Phase 21 with probe config read directly from the protocol (always-on/off
per the compiled YAML, no live toggle) and let Phase 20's console adopt it
later as just another catalog entry. **Recommendation: (b).** Phase 21's
probes are Should-priority and independently valuable; blocking them on
Phase 20's Must-priority toggle console inverts the priority order for no
real technical reason — FR-DASH-12's config is derived the same way every
other instrument setting is (wall #1), Phase 20 or not. Log whichever is
chosen in this phase's deviations log the moment building starts.

## §0 — Traceability spine — do this first

1. Add the **FR-DASH-12** row to `requirements/srs.md` and
   `requirements/traceability.md` §1 (text in § Requirements below, status
   ⬜). FR-INST-19's row already exists — do not re-add.
2. Glossary: **no new terms** — *Accepted chunk* and *Comprehension probe*
   are already defined in `requirements/glossary.md` (added alongside
   FR-INST-19's own SRS row, confirmed present). Use them verbatim; do not
   introduce a synonym.
3. Tracker row: flip this phase's placeholder row in
   `docs/roadmap/README.md`'s "Study conductor (19–21)" table to
   `[21](21-conductor-overlay.md)` / `FR-INST-19, FR-DASH-12` (done as part
   of this spec landing).

No `build-vs-adopt` row needed — VS Code's CodeLens API is already adopted
(`stuckPrompt.ts`); nothing new. No decision-ledger entry — probes are
derived from the protocol like every other instrument, inventing no new
source of truth.

## Slices

### Slice A — Core: the comprehension-probe state machine

`extension/src/core/comprehensionProbe.ts`, vscode-free, injected clock
(mirrors `stuckDetector.ts`'s pattern).

1. **State machine:** `idle → chunk-accepted → probe-pending →
   answered | expired`. A chunk is "accepted" when an `EditBurst` with
   `origin: 'ai'` closes and no undo/redo burst supersedes it within a
   short grace window (reuse the existing burst-classification timing,
   don't invent a second undo-detection mechanism).
2. **Probe bank:** pure generator functions over chunk *metadata only*
   (`linesTouched`, `charsAdded`, `file` extension for language) —
   `predictOutput(meta)` and `locateChange(meta)` — each returning a
   `{promptKind, timeboxMs}` descriptor, never code content. If the
   metadata is insufficient to build a probe (e.g. a one-line burst too
   small to ask "locate the change" meaningfully), skip silently — a
   missed probe opportunity is not an error.
3. **`ChunkReference` type:** `{editBurstId, agentTool?, agentModelId?}` —
   reuses the join keys `behavior.ts` already resolves from workspace
   session state (`session.get('agentTool', '')` etc.), no new provenance
   mechanism.
4. **Tests** (`extension/test/comprehensionProbe.test.ts`, mocked timers):
   an accepted chunk transitions to `probe-pending`; an immediate undo
   cancels it before a probe is shown; an unanswered probe expires at
   `timeboxMs`; the probe descriptor never contains a `code`/`text` field
   (grep-the-output test, FR-ETH-2).

### Slice B — Core: protocol-configured probe cadence (FR-DASH-12)

1. Extend `protocol/src/protocol/derive.py`'s flattening to cover
   `instruments.tern.comprehensionProbe.*` — fields `enabled`
   (bool), `cadence` (`"every-chunk"` | `"sampled"`), `sampleRate` (0–1,
   only meaningful when `cadence: "sampled"`), `probeTypes` (subset of
   `["predict-output", "locate-change"]`). No code change to `_flatten`
   itself (already generic); the addition is declaring the shape in
   example protocols + the derive tests.
2. **Tests:** `derive_overlay_settings` surfaces `comprehensionProbe.*`
   when declared, omitted when absent (no silent default-on).

### Slice C — Adapter: the in-editor prompt

`extension/src/vscode/comprehensionPrompt.ts` (new file, mirrors
`stuckPrompt.ts`'s `CodeLensProvider` + soft-decoration structure — do not
introduce a modal or a second visual language).

1. A `ComprehensionPromptController` subscribing to the core state
   machine's `probe-pending` transitions, rendering a CodeLens above the
   accepted chunk's range with the probe's question (predict-output:
   "What will this print/return?" as a free-text or multiple-choice
   CodeLens action; locate-change: "Which line changed the behavior?" as a
   clickable-range prompt) — reuse `surveys.ts`'s `LikertItem` pattern only
   if a probe needs a confidence rating alongside its answer (optional,
   degrees of freedom below).
2. Wire into `extension.ts` alongside the existing fatigue/stuck
   controllers; gated by the effective `comprehensionProbe.enabled` flag,
   checked at session start only (wall #6 — same discipline as every prior
   phase's config).
3. **Tests:** none new beyond Slice A's core tests + a typecheck/lint pass
   — adapter-level VS Code API behavior is verified by the phase's manual
   walkthrough (Phase 19 established this pattern: `src/vscode` modules
   that call real VS Code APIs are not unit-testable without a mock
   harness this repo doesn't have; don't build one for this phase alone).

### Slice D — Schema bump

1. Bump `SCHEMA_VERSION` to `4` in `extension/src/core/types.ts`; add the
   `comprehension_probe_response` event type carrying the standard join
   keys + `chunkReference` + `promptKind` + `answer` + `correct` (nullable,
   probe-type-dependent) + `msToAnswer` + `expired: boolean`.
2. Update `KNOWN_EVENT_SCHEMA_VERSIONS`-style consumers (middleware's
   `_ProtocolCheck`/ingest schema-version flagging, per NFR-4 — "consumers
   branch on version, never guess") to accept `v4` without treating it as
   unknown.

## Requirements (added to `srs.md` + `traceability.md` in §0)

- **FR-DASH-12 (C)** — The middleware SHALL derive a **comprehension-probe
  config** (enabled, cadence, sample rate, probe-type set) from the
  protocol's `instruments.tern.comprehensionProbe` block, using
  the same derivation path as every other capture setting (wall #1); the
  IDE SHALL apply it only at a session boundary (wall #6). *Traces to:*
  FR-INST-19; wall #1; wall #6.

(FR-INST-19's row already exists in `srs.md`/`traceability.md`; reproduced
here for reference only — do not re-add.)

## Degrees of freedom

- **Probe UI mechanics** — free-text CodeLens input vs. a small QuickPick
  of plausible answers for predict-output; either, as long as it never
  steals focus and always times out cleanly.
- **Confidence rating** — optional add-on reusing `surveys.ts`'s
  `LikertItem`; ship without it if it adds friction the pilot doesn't need.
- **Sampling strategy** — `"every-chunk"` vs `"sampled"` cadence
  implementation detail (a counter vs. a seeded RNG); either, provided it's
  deterministic enough to reason about in a report ("probes ran on ~30% of
  accepted chunks").
- **Which language/file-extensions get probes** — start narrow (the same
  `stuck.languages` allow-list pattern `stuckDetector.ts` already uses) and
  widen later; not a phase-blocking decision.

## Acceptance (maps to fit criteria)

- FR-INST-19: an accepted AI-produced chunk triggers a probe within the
  configured cadence; the recorded response carries the join keys plus a
  `chunkReference` resolvable back to the originating edit burst/agent
  turn; no probe or response ever contains code content beyond FR-ETH-2's
  bound (grep test).
- FR-DASH-12: the config the IDE applies is byte-equal to
  `protocol derive overlay-settings`'s `comprehensionProbe.*` output; a
  change made mid-session does not alter that session (reuses Phase 19's
  proven session-boundary mechanism — a repeat of its own wall-#6 test
  shape, not a new mechanism).
- An ignored probe never blocks the participant and is recorded as
  `expired`, never coerced into an answer (NFR-1).

## Verification steps

1. `uv run pytest && uv run ruff check .` — includes the derive tests for
   `comprehensionProbe.*` and the schema-v4 acceptance in ingest.
2. `extension/`: `npm run check` green — the core state-machine tests
   (accept/cancel/expire), the content-free grep test, typecheck/lint for
   the new adapter file.
3. Manual walkthrough (Extension Development Host, same pattern as Phase
   19's E1): accept an AI-authored chunk → confirm a probe appears
   inline, non-blocking → answer it → confirm the event lands with a
   resolvable `chunkReference` → let a second probe expire unanswered →
   confirm it records `expired`, not a forced answer.
4. NFR-12 evidence: both-theme + reduced-motion screenshots of the inline
   probe CodeLens (mirrors the existing stuck-prompt evidence).
5. Confirm FR-DASH-12's traceability row and this phase's tracker row are
   flipped only after 1–4 are green (golden rule 3).

## Deviations log

Record departures here and in `requirements/traceability.md` §3 as they
occur — in particular, record which sequencing option (a or b, above) was
actually chosen relative to Phase 20.

| Date | Deviation | Reason |
|------|-----------|--------|
| 2026-07-21 | Sequencing option (b): probe config read directly from protocol, no live toggle. | Phase 21 ships before Phase 20's toggle console; probes are independently valuable and blocking them on Phase 20's Must-priority work inverts priorities (see sequencing note §1). Phase 20's console can adopt comprehensionProbe later as a catalog entry. |
| 2026-07-21 | FR-INST-19 marked ✅ (built) though the chunk-reference `agentTool`/`agentModelId` fields will fill from session config at runtime. | The join-key mechanics (behavior.ts + session state) already exist; the probe machine and adapter ship end-to-end. Per-chunk resolution is delegated to the wiring in extension.ts. |
| 2026-07-21 | SCHEMA_VERSION bumped from 3 to 4; middleware already accepted v4 via KNOWN_EVENT_SCHEMA_VERSIONS since the agent-interaction leg work (Phase 07). | No middleware changes needed; bump is the event-shape contract update for `comprehension_probe_response`. |
