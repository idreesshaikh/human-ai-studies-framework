# Phase 20: The Capture Console (study conductor, part 2 of 3)

> Self-contained: execute this file in a fresh session at the repo root.
> Read first: `docs/VISION.md`, `docs/roadmap/README.md` (the walls +
> autonomy charter (wall #6 in particular), `docs/roadmap/19-live-capture-link.md`
> (the channel this phase builds a control surface on top of),
> `docs/roadmap/18-evolution.md` (the amendment engine this phase routes
> every toggle through: there is no second config-mutation path),
> `requirements/specs/fr-conv.md` (the grounding contract, FR-CONV-2),
> `extension/PROJECT_GUIDE.md` (the core/adapter split).

**Depends on:** Phase 19 (`EnrollmentToken`, `middleware/src/middleware/enrollment.py`'s
`build_capture_config`/`enabled_instruments`, `platform/src/components/enrollment/EnrollmentPanel.tsx`'s
read-only capture-config chips), Phase 18 (`compiler.py`'s `_apply_instrument_moves`,
`evolution.py`'s `consent_relevance`/`CONSENT_SUBKEYS`, `StudyEvolution.pending_reapproval`),
FR-CONV-2 (grounding).
**Satisfies:** FR-INST-18 (IDE health/diagnostics stream), FR-DASH-11 (grounded
per-metric toggle UI, new), FR-CONV-7 (consent-relevance covers metric-level
toggles, new).
**Elicited:** implied by Phase 19's own scope note: "Phase 20 ('the capture
console') builds the grounded per-metric toggle UI on the channel this phase
opens", formalized 2026-07-21 while auditing the roadmap for unspecced
phases.
**Status:** ✅ built: toggle-as-amendment endpoint + catalog + FR-CONV-7
consent-relevance + `IdeHealthCollector` + `TogglePopover`, all pytest +
`node:test` + build verified. See the deviations log below.

## The idea

Phase 19 gave a researcher a *window* onto the capture config each paired
participant runs under: `EnrollmentPanel`'s chips render `enabledInstruments`
read-only. That's visibility without control: to actually change what's
captured, a researcher must still go back through the conversational
designer, propose a new instrument config, compile, and approve: clumsy
for "just turn stuck-detection on for P04." Phase 20 makes each chip a
**control**: click a metric, see why it matters (a grounded rationale:
citations into the corpus/SRS, or `grounding: none` labeled honestly per
FR-CONV-2), flip it, and the toggle becomes a `reconfigure` move applied
through the *exact same* amendment path Phase 18 built: `compile_moves`,
`consent_relevance`, `pending_reapproval`, never a parallel mutation
mechanism. No new way for the protocol to change; the same document of
record, reached from a faster door.

It also lands the first genuinely new capture stream since the four legs
were built: FR-INST-18, an IDE health/diagnostics count (errors/warnings,
build/test invocations), proving the toggle console on a real, previously
unbuilt metric rather than only re-skinning the four legs' existing flags.

This is **part 2 of the study-conductor arc**: Phase 19 built the link,
Phase 20 builds the control surface, Phase 21 enriches what the participant
sees. Unbuildable before 19 (needs its config channel); Phase 21 does not
depend on this phase's toggle UI shipping first (see Phase 21's own
dependency note on sequencing).

Non-negotiable bounds, inherited verbatim:

- **Wall #6, hard.** A toggle is an amendment, applied at the *next* session
  boundary, never mid-run. Nothing here reopens that door; it reuses
  Phase 19's `refreshConfigAtSessionStart` gate unchanged.
- **Wall #1.** The protocol is still the sole document of record. A toggle
  is a `reconfigure` move through `compile_moves`, not a side-channel write
  to `EnrollmentToken` or any other table.
- **Wall #2.** No LLM in the compile step. A toggle's patch is
  deterministic: `{section: "instruments", name, op: "reconfigure", path,
  value}`, built by the platform from the clicked chip, never proposed by
  the assistant.
- **FR-CONV-2, grounding.** Every togglable metric's rationale is either
  cited (corpus/SRS/glossary) or explicitly labeled unsourced, never
  silently uncited.
- **No new dependency** (NFR-10). Same stack throughout.

## §0: Traceability spine, do this first

1. Add **FR-DASH-11** and **FR-CONV-7** rows to `requirements/srs.md` and
   `requirements/traceability.md` §1 (text in § Requirements below; status
   ⬜ until verified). FR-INST-18 already has rows; do not re-add, just
   confirm its status flips to ✅ alongside the other two once this phase
   is verified.
2. Add glossary terms (`requirements/glossary.md`): none new; this phase
   reuses *pairing token*, *capture config*, *enrollment* verbatim (Phase
   19) and *design move*/*grounding* (Phase 15/18). Confirm no new bare
   synonym creeps in ("metric toggle" is fine as plain English, not a
   glossary term).
3. Add the tracker row: this phase already has a placeholder row in
   `docs/roadmap/README.md`'s "Study conductor (19–21)" table: flip its
   link from bare text to `[20](20-capture-console.md)` and its Satisfies
   column to `FR-INST-18, FR-DASH-11, FR-CONV-7` (done as part of this
   spec landing; verify it's not stale).

No `build-vs-adopt` row needed (NFR-10 satisfied by reuse: VS Code
Diagnostics API is a built-in, `compile_moves`/`consent_relevance` already
exist). No decision-ledger entry needed (nothing new is adopted; the
protocol stays the sole source of truth).

## Slices

### Slice A: Backend (the toggle-as-amendment endpoint)

Middleware only.

1. **Extend `consent_relevance`** (`middleware/src/middleware/evolution.py`).
   Today's subkey loop (`CONSENT_SUBKEYS = {"contentPolicy", "capture",
   "redaction", "record", "scopes", "raw", "adapter"}`) only inspects an
   instrument's *top-level* keys: a nested change like
   `tern.stuck.enabled` is invisible to it (confirmed by
   reading the function directly: it diffs `before_instr[name]` /
   `after_instr[name]` as flat dicts one level deep). Add a recursive
   "did any sub-key literally named `enabled` change, or did a
   previously-absent metric subtree appear" check, walking each
   instrument's full nested dict. This is FR-CONV-7. Table-driven test:
   toggling `stuck.enabled` from `true`→`false` must now return
   `relevant=True`; toggling `stuck.thresholdSeconds` must not (unchanged
   behavior, F4.2's "a threshold/interval tweak is not consent-relevant").

2. **`POST /studies/{study_id}/enrollment/toggles`** (role-gated,
   `toggle_capture` capability (researcher+; ethics-gated same as mint).
   Body `{instrument, path: string[], value, rationale?: string}`.
   Builds the deterministic move
   `{section: "instruments", name: instrument, op: "reconfigure", path,
   value}`, applies it via `compiler._apply_instrument_moves` against the
   study's current approved YAML (reuse `_resolve_study_protocol`), then
   calls `consent_relevance(before, after)`. If relevant: record an
   `Amendment` row exactly as Phase 18's compile-approve path does
   (`evo.pending_reapproval = amend.id`) and return `{applied: True,
   requiresReapproval: True, amendmentId}`. If not relevant: commit the new
   approved snapshot directly (no re-approval ceremony, F4.2's whole
   point) and return `{applied: True, requiresReapproval: False}`. Never a
   third state; the endpoint is total over its two `consent_relevance`
   outcomes.

3. **`GET .../enrollment/toggles/catalog`**: the list of togglable
   metrics for a study's protocol shape, each `{instrument, path, label,
   grounding: {citations: [...]} | {unsourced: true}, currentValue}`.
   Grounding source: a small static table in `enrollment.py` mapping known
   metric paths (`stuck`, `fatigue`, `ideHealth`, …) to corpus refs already
   cited elsewhere in the codebase (e.g. `docs/papers/README.md`'s Tier A
   entries) or `unsourced: true`, never invented citations (FR-CONV-2:
   "may only cite sources retrieved in that exchange" extends here as
   "only cite sources already in the corpus/SRS, never fabricate a new
   one for this endpoint").

4. **Tests:** consent-relevance regression (nested-enable case); toggle
   endpoint records an amendment and gates re-approval when relevant, skips
   it when not; catalog endpoint never emits a citation absent from
   `docs/papers/` or `requirements/`; the whole toggle path never writes
   outside `compile_moves` (grep the diff, no direct `EnrollmentToken`
   mutation).

### Slice B: Backend (FR-INST-18, the IDE health stream)

1. **Schema.** Add `instruments.tern.ideHealth` to
   `protocol/src/protocol/derive.py`'s flattening (no code change needed
   beyond declaring the shape in an example protocol; `_flatten` already
   walks arbitrary nesting). Fields: `enabled` (bool), `debounceSeconds`
   (int). A schema-v4 candidate event type `ide_health` carrying
   `errorCount`, `warningCount`, `buildInvocations`, `testInvocations`
   since the last tick, content-free by construction (counts, never
   diagnostic messages or file paths beyond FR-ETH-2's aggregate-only
   bound).
2. **Tests:** `derive_overlay_settings` includes `ideHealth.*` when present;
   omitted entirely when the instrument block doesn't declare it (no
   default-on surprise).

### Slice C: Extension (the diagnostics collector)

`src/core`/`src/vscode` split, per `PROJECT_GUIDE.md`'s sacred rule.

1. **Core** (`extension/src/core/ideHealth.ts`, vscode-free): a pure
   debounced counter: `record(kind: 'error'|'warning'|'build'|'test')`,
   `flush(): {errorCount, warningCount, buildInvocations,
   testInvocations}`, injected clock for the debounce window (mirrors
   `stuckDetector.ts`'s pattern).
2. **Adapter** (`extension/src/vscode/ideHealth.ts`, new): subscribes to
   `vscode.languages.onDidChangeDiagnostics`, feeds counts into the core
   module; a task-execution listener increments build/test invocation
   counts. Gated by the effective `tern.ideHealth.enabled` flag
   exactly like every other capture stream (checked at session start,
   never mid-session (wall #6, same discipline as every Phase 19/20
   config).
3. **Tests** (`extension/test/ideHealth.test.ts`): debounce behavior with
   mocked timers; the emitted event never carries a diagnostic message
   string or file path (grep-the-output test, FR-ETH-2).

### Slice D: Platform (the console)

1. **`EnrollmentPanel`'s chips become buttons.** Clicking a chip opens a
   popover: current value, the grounding rationale (cited or
   `data-agent-status="unsourced"`, reusing `MoveCard`'s unsourced-label
   pattern), and a toggle control. Confirm via the catalog endpoint
   (Slice A.3) before rendering: never show a toggle for a metric the
   protocol doesn't declare.
2. **Submit** calls the Slice A.2 endpoint; on `requiresReapproval: true`,
   render the existing `AmendmentBanner` (Phase 18, reused verbatim; no
   new banner component) in its paused state; on `false`, the chip updates
   optimistically and no ceremony interrupts the researcher.
3. **Capability:** add `"toggle_capture"` to `platform/src/lib/capabilities.ts`'s
   `Capability` union and `MATRIX` (researcher+, mirroring `mint_token`).
4. **NFR-12:** both-theme + reduced-motion screenshots of the popover and
   the re-approval-paused state; axe clean; keyboard-complete
   click-to-toggle path (a chip is a `<button>`, not a `<div onClick>`).

## API surface (additions)

```
POST /studies/{id}/enrollment/toggles           apply one metric toggle as an amendment (researcher+, ethics-gated)
GET  /studies/{id}/enrollment/toggles/catalog   togglable metrics + grounding + current value (researcher/viewer)
```

## Requirements (added to `srs.md` + `traceability.md` in §0)

- **FR-DASH-11 (M)**: The platform SHALL let a researcher toggle an
  individual capture metric on or off from the enrollment surface, each
  toggle grounded (cited or explicitly labeled unsourced per FR-CONV-2)
  and applied as a protocol amendment through the existing evolution
  engine (FR-CONV-4/5); never a second configuration-mutation path. A
  consent-relevant toggle pauses new sessions pending re-approval; a
  non-relevant toggle (a threshold/interval-class change) applies
  immediately. *Traces to:* FR-DASH-10; FR-CONV-4/5; FR-CONV-2; the
  platform loop's live-data rung.
- **FR-CONV-7 (S)**: The evolution engine's `consent_relevance` check
  SHALL treat a change to a metric's `enabled` state, and the first
  appearance of a previously-undeclared metric subtree, as consent-relevant,
  not only the top-level instrument-presence and fixed-subkey checks it
  performs today. *Traces to:* FR-CONV-4.2; wall #6 wall-adjacent (the
  toggle console is where this gap would otherwise surface as a silent
  under-approval bug).

(FR-INST-18's row already exists in `srs.md`/`traceability.md`; reproduced
here for reference only, do not re-add.)

## Degrees of freedom

- **Grounding-table shape**: a static Python dict, a small YAML file, or
  reuse of the existing corpus-index matching machinery; any, as long as
  it never fabricates a citation absent from the corpus/SRS.
- **Popover vs. inline expand** for the chip-to-control interaction; either,
  within NFR-12's registers.
- **Which metrics ship togglable at launch**: start with `stuck`,
  `fatigue`, and the new `ideHealth`; expanding the catalog to every leg's
  flags is additive and doesn't block the phase's acceptance.

## Acceptance (maps to fit criteria)

- FR-DASH-11: a researcher can flip `stuck.enabled` from the dashboard and
  see the resulting `captureConfigVersion` change reflected in Phase 19's
  `/capture-config` endpoint; a consent-relevant toggle visibly pauses new
  pairings/sessions until re-approved (reusing Phase 18's existing gate,
  proven by its own tests; this phase adds the trigger, not the gate).
- FR-CONV-7: a test proves `consent_relevance` now flags a nested
  `enabled` change it previously missed, with no change to its existing
  threshold-tweak-is-not-relevant behavior.
- FR-INST-18: the IDE health stream lands events with `errorCount` etc.,
  content-free (grep test), togglable through the same console.
- Wall #6: a toggle applied while a session is running does not alter that
  session; it takes effect only at the next session start (reuses Phase
  19's `refreshConfigAtSessionStart`/`shouldApplyCaptureConfig`, no new
  test needed here beyond confirming the toggle path feeds the same
  `captureConfigVersion` mechanism, not a bypass).

## Verification steps

1. `uv run pytest && uv run ruff check .`: includes the consent-relevance
   regression, the toggle-endpoint tests, and the IDE-health derive tests.
2. `extension/`: `npm run check` green, covering `ideHealth.ts` core + adapter
   tests, debounce behavior, content-free grep test.
3. `platform/`: `npm run build && npm run lint` green; agent-annotations +
   no-raw-literal checks green for the new popover/toggle UI.
4. Manual walkthrough: toggle a consent-relevant metric → confirm the
   amendment banner pauses new pairing/sessions → re-approve → confirm the
   *next* session's pre-flight reflects the change and the currently-open
   session (if any) does not.
5. NFR-12 evidence archived for the popover + paused-banner states.
6. Confirm FR-DASH-11, FR-CONV-7, and FR-INST-18's traceability rows and
   this phase's tracker row are flipped only after 1–4 are green (golden
   rule 3).

## Deviations log

Record departures here and in `requirements/traceability.md` §3 as they
occur.

- **2026-07-21: `TogglePopover` renders its own compact "Amendment
  pending" note rather than embedding `AmendmentBanner` verbatim.** Slice
  D.2 called for reusing `AmendmentBanner` "no new banner component," but
  `AmendmentBanner` is a page-level, study-wide surface (bound to
  `useEvolution()`'s `amendmentState`) that doesn't fit inside a small
  toggle popover's DOM context. `AmendmentBanner` still renders at the
  `StudyHome` level reflecting the same paused state (Phase 18's existing
  wiring, untouched); the popover's inline note is an immediate,
  contextual confirmation of what the toggle just did, not a second source
  of truth. Accepted as a reasonable embedding-context adjustment, not a
  functional gap.
- **2026-07-21: a real bug found and fixed during alignment review:**
  `EnrollmentPanel.tsx`'s chip→catalog match used
  `c.path.length === 1 && c.path[0] === i.name`, which never matches any
  `tern` catalog entry (all of them are 2-segment paths like
  `["stuck", "enabled"]`), clicking a chip silently did nothing, making
  the toggle console unreachable through its intended entry point. Fixed
  to match on `path[0] === i.name && path[last] === "enabled"`.
- **2026-07-21: a second bug found and fixed:** `VscodeIdeHealthAdapter`
  and `IdeHealthCollector` were both built and unit-tested (Slice C) but
  never instantiated anywhere in `extension.ts`; no IDE health event was
  ever actually emitted in a real session. Wired into `bootSession`
  (gated on `tern.ideHealth.enabled`, read at session start
  only per wall #6) and disposed in `teardownStudy`, mirroring the
  `comprehensionProbe`/`comprehensionPrompt` wiring pattern Phase 21
  established.
