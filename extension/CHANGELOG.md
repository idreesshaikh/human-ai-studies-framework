# Changelog

All notable changes to the Cognitive Overlay extension are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-07-11

The behavioral telemetry leg (MP-05, decision D12: same extension, same sink
pipeline). Event schema version bumped to **3**.

### Added

- **Editor focus tracking** - `editor_focus` events on active-editor and
  window-state changes, debounced 250 ms (rapid tab-cycling records
  first + last).
- **Scroll coverage** - `visible_range` events (top/bottom/total lines),
  debounced 500 ms per editor.
- **Edit bursts with origin classification** - `edit_burst` events
  aggregating changes until a 2 s gap or file switch, classified
  `human` / `ai` / `paste` / `undo-redo` with protocol-configurable
  thresholds; sizes and shapes only, never content.
- **Clipboard paste telemetry** - `clipboard_paste` events with size, line
  count, and `msSinceInternalCopy` via a salted in-memory hash correlation;
  the clipboard is never read.
- **AI-completion lifecycle** - `ai_suggestion` events
  (shown / accepted / dismissed) with review latency (`visibleMs`), via a
  passive inline-completion provider plus session-scoped Tab/Esc wrapper
  keybindings; block-injection heuristic as fallback. Blind spots documented
  in `docs/adaptation-notes.md`.
- **Save + heartbeat events** - `file_save` sizes and `heartbeat`
  active/idle transitions over a rolling 120 s window.
- **Environment snapshot** - `environment_snapshot` at session start
  (VS Code version, AI-relevant extension versions, OS, agent tool/model,
  task ID) for replication provenance.
- **Capture filter** - behavioral capture restricted to configured languages
  (pilot: Python) and workspace-internal files.
- **`cognitiveOverlay.behavior.*` settings** - per-signal switches and all
  heuristic thresholds; `cognitiveOverlay.session.*` provenance fields.

## [0.1.0] - 2026-07-07

Initial release - the cognitive / self-report leg of the developer-study
framework.

### Added

- **Session clock** - start a session with a participant ID and A/B condition
  (`ai-assisted` / `unassisted`); sleep-safe, pausable, and crash-resumable.
  A status-bar countdown is the only permanent UI.
- **In-flow fatigue sampling** - a 7-point Likert QuickPick that waits for a
  typing pause before appearing, with configurable interval, jitter, and a
  quiet tail near session end.
- **Stuck detection** - dwell and scroll-thrash heuristics that draw a soft
  inline border around the code with CodeLens actions, never stealing focus.
- **End-of-study debrief** - a NASA-TLX-inspired webview survey on the same
  7-point scale, with an extra AI-reliance item in the AI-assisted condition.
- **Research-ready output** - one JSON Lines file per session, optionally
  mirrored to an HTTP middleware endpoint. The local file is always the source
  of truth.
- **Portable core** - session clock, heuristics, surveys, and recorder live in
  `src/core` with zero IDE imports, unit-tested with `node:test`, so a
  JetBrains port only re-implements the thin `src/vscode` adapter.
