# Mega-Prompt 05 - Behavioral Telemetry (third instrument leg)

> Self-contained: execute this file in a fresh working session at the repo
> root. Read first: `docs/archive/roadmap/00-VISION.md`, `requirements/srs.md`,
> `requirements/build-vs-adopt.md` (D2–D4, D12),
> `extension/docs/developer_behavior_capture.md`, and
> `extension/PROJECT_GUIDE.md` (architecture + conventions).

**Depends on:** 04 (middleware to receive it) - but JSONL-only development
works before 04 exists.
**Satisfies:** FR-INST-5, FR-INST-8, FR-INST-9, FR-INST-10, FR-INST-11,
FR-INST-12, FR-INST-13 (glass styling pass), FR-INST-14 (environment
snapshot); bound by FR-ETH-2, NFR-1, NFR-3. **Sprint day 4 (with MP-12).**
**Status:** ✅ Done (2026-07-11) - see the MP-05 row in
`requirements/traceability.md` §3 for deliverables and deviations.

## Context

The third leg from the root README, specified in
`extension/docs/developer_behavior_capture.md`. Per decision **D12** this is NOT a new
plugin: it extends the existing Cognitive Overlay (one install, one sink
pipeline, one core/adapter discipline). Three open-source plugins are the
studied references - adapt their patterns, do not vendor their code:

- **Tako** (`si-codelounge/tako`) - how to hook text-document mutations and
  the inline-completion lifecycle to detect AI accept/reject and measure
  review time (D2).
- **ActivityWatch** (`ActivityWatch/aw-watcher-vscode`) - the dumb-sensor →
  local-daemon pattern: fire-and-forget JSON events, zero typing latency
  (D3). Our daemon is the MP-04 middleware on :8000.
- **WakaTime** (`wakatime/vscode-wakatime`) - active-vs-idle heartbeat model
  and language/path filtering (D4).

Before writing code, skim all three repos (entry point + event hooking
files) and note in a short `extension/docs/adaptation-notes.md` what was taken from
each - this is NFR-10 evidence.

## Deliverables

### 1. New event types (bump `SCHEMA_VERSION` in `src/core/types.ts`)

Every payload below rides the existing StudyEvent envelope (join keys come
free from `Recorder`). Document each in the README event table.

| type | payload (all FR-ETH-2-safe - sizes/shapes/timings, never content) |
| ---- | ------------------------------------------------------------------ |
| `editor_focus` | `{ file: <workspace-relative path or "external">, languageId, groupCount }` on active-editor change; `{ state: focused\|blurred }` on window state. Debounce 250 ms (rapid tab-cycling emits first+last). |
| `visible_range` | `{ file, topLine, bottomLine, totalLines }` on scroll/resize, debounced 500 ms per editor. Feeds scroll coverage (FR-INST-9). |
| `edit_burst` | `{ file, charsAdded, charsDeleted, linesTouched, durationMs, origin }` - a burst closes after 2 s without edits or on file switch. `origin ∈ human\|ai\|paste\|undo-redo` (FR-INST-10, logic below). |
| `clipboard_paste` | `{ charCount, lineCount, msSinceInternalCopy?, targetFile }` - `msSinceInternalCopy` present only when the copy happened inside the workspace this session (else the paste came from outside: browser, AI chat pane…). Content: NEVER; a salted session-local hash may be kept in-memory only for the internal-copy correlation, never written. |
| `ai_suggestion` | `{ suggestionId, action: shown\|accepted\|rejected\|dismissed, visibleMs?, charCount?, lineCount? }` (FR-INST-8). `visibleMs` on the decision event = review latency. |
| `file_save` | `{ file, charCount, lineCount }` |
| `heartbeat` | `{ state: active\|idle }` transitions only (not periodic spam) - active = any interaction within a rolling 120 s window (FR-INST-11). |
| `environment_snapshot` | `{ vscodeVersion, extensionVersions: {...}, os, agentTool?, agentModelId?, taskId }` once at session start (FR-INST-14) - replication provenance. |

Also in this phase, the **glass HUD styling pass** (FR-INST-13): the debrief
webview is already glassmorphic - bring the fatigue probe up to the same
standard (webview-based translucent HUD floating over the editor, iOS-glass
aesthetic: blur, transparency, minimal chrome) where the VS Code API allows;
where it doesn't (QuickPick styling is locked), document the constraint in
`extension/docs/adaptation-notes.md` and keep the QuickPick fallback. The invariant
either way: the participant never leaves the editor, and the prompt never
takes focus from the code (NFR-1).

### 2. Core logic (`src/core/behavior.ts` + friends) - NFR-3: zero `vscode` imports

- **Burst aggregator**: consumes primitive change signals
  `{fileKey, charsAdded, charsDeleted, lines, tsMono}`; closes bursts on the
  2 s gap / file-switch rule; injected clock; unit-tested with mocked timers
  exactly like `stuckDetector`.
- **Origin classifier** (FR-INST-10), priority order per burst:
  1. `undo-redo` - signal flagged by the adapter (VS Code marks these).
  2. `ai` - burst correlates with an `ai_suggestion accepted` within
     500 ms, **or** single change ≥ `aiBlockCharThreshold` (default 80)
     chars landing in ≤ 50 ms (the behavior doc's "massive block in 1 ms").
  3. `paste` - correlates with a clipboard-paste signal within 100 ms.
  4. `human` - otherwise.
  Thresholds injected via config (protocol-derivable, FR-PROT-4); the
  heuristic and its failure modes documented in the module docstring.
- **Idle detector** (FR-INST-11): rolling-window state machine emitting
  transitions; window size injected.
- **Capture filter** (FR-INST-12): predicate over `{languageId, path}`
  from config (pilot: `["python"]`, workspace-internal only); applied in
  core so it's testable.

### 3. Adapter wiring (`src/vscode/behavior.ts`, extend `signals.ts`)

- `window.onDidChangeActiveTextEditor`, `onDidChangeWindowState` →
  `editor_focus`; `onDidChangeTextEditorVisibleRanges` → `visible_range`;
  `workspace.onDidChangeTextDocument` (reason field distinguishes
  undo/redo) → burst signals; `onDidSaveTextDocument` → `file_save`.
- Paste detection: intercept via a wrapped
  `editor.action.clipboardPasteAction` command registration (measure size
  from the resulting document change; never read clipboard text) - check
  how Tako/WakaTime handle this before choosing the mechanism.
- AI lifecycle: VS Code has no single public "completion accepted" event -
  study Tako's approach (D2); combine inline-completion provider hooks,
  command interception, and the ≥-threshold injection heuristic as
  fallback. Whatever is chosen, document the mechanism's blind spots in
  `extension/docs/adaptation-notes.md` (this is RQ-F1 evidence either way).
- Config namespace `cognitiveOverlay.behavior.*`: per-signal booleans +
  thresholds, all with defaults matching the above.

### 4. Constraints (non-negotiable)

- `src/core` never imports `vscode` (NFR-3).
- No raw code/keystrokes/clipboard content/off-workspace paths (FR-ETH-2).
- A failing sensor never interrupts the participant; swallow, count,
  report once (NFR-1). No perceptible typing latency - all handlers O(1),
  heavy work in the burst aggregator's timer, events fire-and-forget.
- `npm run check` stays green; new core logic gets mocked-timer tests
  (burst windowing, origin priority, idle transitions, filter).

## Acceptance criteria

- A dev-host session doing: type → paste a block → accept an AI/large
  injection → scroll → idle 3 min → save, yields JSONL containing all seven
  event types with correct origins (`human`, `paste`, `ai`), one idle
  transition pair, and plausible `visibleMs`/`msSinceInternalCopy`.
- Events flow through the existing HttpSink to the middleware unchanged.
- A non-Python file edit produces zero behavioral events (filter works).
- `SCHEMA_VERSION` bumped; README event tables updated;
  `extension/docs/adaptation-notes.md` records what was taken from Tako/AW/WakaTime.

## Verification

- `npm run check`; run the scripted dev-host scenario above, inspect the
  JSONL line-by-line against the table, confirm middleware ingestion and
  that the events appear in the MP-06 timeline view if built. Update
  `docs/archive/roadmap/00-VISION.md` tracker + `requirements/traceability.md`
  (FR-INST-5,8–12 → ✅; FR-ETH-2, NFR-1 → ✅ overall).
