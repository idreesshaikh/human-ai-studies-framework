# Phase 25 — The Instrument Surface (the extension becomes the study)

> Self-contained: execute this file in a fresh session at the repo root.
> Read first: `docs/VISION.md`, `docs/roadmap/README.md` (the walls +
> autonomy charter — walls #1 and #6 in particular),
> `docs/roadmap/19-live-capture-link.md` (the pairing channel this phase
> renders), `docs/roadmap/20-capture-console.md` (the toggle catalog this
> phase extends and consumes), `extension/PROJECT_GUIDE.md` (the core/adapter
> split — `src/core` never imports `vscode`),
> `requirements/specs/nfr-12-experience.md` (the experience bar applies to the
> extension's surfaces too).

**Depends on:** Phase 19 (`pairing.ts`, `captureConfig.ts`,
`connectionString.ts`, `refreshConfigAtSessionStart`), Phase 20
(`enrollment.py`'s `_TOGGLE_CATALOG` / `toggle_catalog`, the platform's
`TogglePopover`), Phase 21 (`comprehensionProbe`).
**Satisfies:** FR-INST-22 (IDE sidebar leg surface, new), FR-DASH-13
(toggle catalog spans all four legs, new), FR-OPS-8 (extension is a
publishable artifact, new).
**Elicited:** owner, 2026-07-26 — "the idea of the VS Code extension was to
integrate all four legs … these are all enabled from the platform … the
generated mint link goes into the VS Code extension for recording … extension
properly appears in the side bar not as teeny tiny in the lower bar … near
complete to be published in the app store. This is the study out of the box
platform."
**Status:** Specced (2026-07-26). Slices A–D built (2026-07-26); see the
deviations log for what changed during the build and what remains owner-run.

## The idea

The extension is the only part of PHOENIX a participant ever touches, and
today it is a countdown in the corner of the status bar. Everything the
platform knows about a study — which legs are running, what each one
captures, what the participant consented to — is invisible at the exact
moment it matters most, inside the editor, while the session runs.

Phase 25 promotes the instrument to a first-class **sidebar surface**: an
activity-bar container whose views answer, at a glance, the three questions
a participant and a researcher both have. *Am I in a session?* *What is
being captured right now, across all four legs?* *Where is my data going?*

Three things make this more than a UI move:

1. **All four legs, visible together.** The static-metrics, behavioral,
   cognitive, and agent-interaction legs are shown as one list with a real
   on/off state resolved from the capture config — including legs the
   protocol leaves off, which are rendered *off, not hidden*. A consent
   promise you can only verify for three of four legs is not a consent
   promise.
2. **One catalog, two renderers.** The leg surface renders the same
   `toggle_catalog` the platform's capture console renders (FR-DASH-13),
   extended in this phase to cover the static-metrics leg. The IDE never
   grows its own list of what a leg does; a leg description written once is
   correct in both places or wrong in neither.
3. **Installable.** FR-OPS-8 closes the loop the mint link opened: install
   from the Marketplace, redeem a token, record. No clone, no build.

### What this phase deliberately is not

- **Not a reimplementation of the Python legs.** `metrics/` runs over
  committed code and `agent-capture/` over Claude Code transcripts; both stay
  where they are. The extension *surfaces and controls* four legs; it hosts
  two. Anything else would drag `vscode` into places it must not go and
  duplicate analysis code in TypeScript.
- **Not a second config-mutation path.** The sidebar is read-mostly: it
  renders the capture config and links back to the platform's console.
  Where it does offer a control, that control is a `reconfigure` amendment
  through `compile_moves` exactly as Phase 20 built it — never a local write.

Non-negotiable bounds, inherited verbatim:

- **Wall #1.** The protocol is the sole document of record. The sidebar
  displays derived state; it never becomes a place study configuration
  lives.
- **Wall #6, hard.** Nothing in the sidebar reconfigures a running session.
  A toggle reached from the IDE takes effect at the next session boundary
  via the unchanged `refreshConfigAtSessionStart` gate, and the surface must
  *say so* when a change is pending rather than implying it took effect.
- **Never interrupt the participant** (NFR-1/2). The sidebar is passive. It
  does not steal focus, does not auto-reveal mid-session, and its failure to
  render never touches the recorder — local JSONL remains the source of
  truth.
- **Privacy by construction.** The surface shows *shapes and states*, never
  captured content. It is a natural place to leak a file path or a snippet;
  it must not.
- **`src/core` never imports `vscode`** (`extension/PROJECT_GUIDE.md`). Leg
  state derivation is core and unit-tested there; the tree/webview provider
  is adapter-only.

## Slices

### Slice A — the catalog spans four legs (FR-DASH-13)

Extend `_TOGGLE_CATALOG` in `middleware/src/middleware/enrollment.py` to the
static-metrics leg and complete the `agentCapture` entries, each with the
grounded rationale FR-CONV-2 requires (a citation into the corpus/SRS, or
`grounding: none` labeled honestly — never a fabricated one). Add a `leg`
field to every catalog entry so consumers can group by leg without
string-matching instrument names.

**Fit criteria.** `toggle_catalog` returns entries for all four legs given a
protocol enabling all four; every entry carries `leg`, `label`,
`description`, `grounding`, `currentValue`; a protocol enabling two legs
returns those two legs' entries and marks the rest absent; no entry invents
a citation. pytest.

### Slice B — leg state as core logic (FR-INST-22, portable half)

A new `extension/src/core/legs.ts`: given a `CaptureConfig` and the session
state, derive the four legs' display state (`enabled | disabled | unavailable`,
plus what the leg captures in participant-facing words and its consent
relevance). Pure functions, no `vscode` import, exhaustively tested —
including the "protocol enables nothing" and "config not yet pulled" cases,
which are the ones that will otherwise render as a confidently wrong "off".

**Fit criteria.** `node:test` covers all four legs × (enabled/disabled/
unavailable); a leg absent from the config is `unavailable`, never `disabled`;
no `vscode` import (the existing core/adapter lint stays green).

### Slice C — the sidebar (FR-INST-22, adapter half)

`contributes.viewsContainers.activitybar` with a TERN container and icon, and
`contributes.views` with three: **Session** (state, remaining time, the
start/pause/end actions currently buried in `tern.statusMenu`), **Capture**
(the four legs from Slice B, each expandable to its catalog entries), and
**Data** (output directory, ingest endpoint, queue depth / `seq` gaps so loss
stays detectable per NFR-2). A `TreeDataProvider` per view — not a webview:
it inherits VS Code's theming, keyboard navigation, and accessibility for
free, which is most of NFR-12's bar met by construction rather than by
re-implementation. The status-bar item stays as a compact session indicator
and stops being the only way in.

**Fit criteria.** The container appears in the activity bar with the four
legs listed under Capture, disabled legs shown as off; every action reachable
by keyboard; the views render correctly with no study paired (the empty state
explains how to pair, per the writing guidance — an empty screen is an
invitation to act); Extension Dev Host walkthrough, both themes.

### Slice D — publishable (FR-OPS-8)

Real `publisher`, `icon`, `categories`, `repository`, explicit
`activationEvents`, README/CHANGELOG/LICENSE fit for a Marketplace listing,
`vsce package` wired into the release-tag workflow beside the container image,
and a bundling pass so the `.vsix` is not the raw `out/` tree.

**Fit criteria.** `vsce package` produces a `.vsix` with no warnings; a clean
VS Code install of that `.vsix` can redeem a pairing token and record a
session end-to-end against a local middleware; `npm run check` green.

## Verification

1. `uv run pytest && uv run ruff check .` — Slice A.
2. `npm run check` in `extension/` — Slices B–D.
3. Extension Dev Host walkthrough: pair via a minted link, confirm all four
   legs render with the states the protocol implies, run a session, confirm
   the sidebar never steals focus and the status bar still ticks.
4. Wall #6 check: flip a toggle in the platform console mid-session; the
   sidebar shows the change as *pending*, and it applies only at the next
   session start.
5. Install the packaged `.vsix` into a clean VS Code and repeat step 3.

## Deviations log

- **Slice B needed a middleware change the spec did not anticipate.** The
  capture config the IDE receives carries only the flat `tern.*` settings, so
  two of the four legs are invisible to it — `legs.ts` could not have derived
  their state from anything it had. `build_capture_config` now carries the
  `leg_summary` alongside `settings` as a purely descriptive field. Only
  `settings` is ever applied, so this cannot widen what is captured. Recorded
  because it moved work across the middleware/extension boundary the spec drew.
- **`readLegs` grew a third state beyond the spec's two claims.** `unavailable`
  is distinct from `disabled` because "the protocol doesn't configure this leg"
  and "we have not fetched a config yet" must never render as "switched off".
  Malformed or absent payloads degrade to `unavailable` rather than being
  trusted.
- **Two packaging bugs found and fixed by running `vsce ls`, not by review.**
  The first `.vscodeignore` shipped the `out-tests/` build, and its `media/*.svg`
  rule excluded `media/tern.svg` — the activity-bar icon the manifest points at
  — which would have shipped an installable extension with no sidebar icon.
- **Session event counts deferred.** `DataView` is written to show
  written-vs-mirrored counts so `seq` gaps stay visible (NFR-2), but the
  recorder does not currently expose them; the rows are omitted rather than
  faked. Plumbing them is the one piece of Slice C left.

**Owner-run, still open:** the Extension Dev Host walkthrough (verification
steps 3–5, both themes) and a Marketplace publisher id + `VSCE_PAT`. Neither
can be done by a builder: the first needs a live editor, the second an account
registration.
