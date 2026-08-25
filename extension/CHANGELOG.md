# Changelog

All notable changes to the TERN extension are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.1] - 2026-08-25

This patch release makes prepared studies easier to inspect and safer to run.

### Added

- Prepared session manifests can supply a task and one-use session ID.
- Preflight shows external producer availability and explains when a producer
  must be run separately.
- Pairing refreshes the participant sidebar immediately after consent.

### Changed

- Session records carry the assigned task ID so live and analysed sessions can
  be distinguished without relying on participant and condition alone.
- Capture configuration keeps producer capability state separate from receipt
  of actual events.

## [1.0.0] - 2026-08-22

TERN is ready for its first public release. This release packages the complete
study-participant path: safe pairing, consent before capture, protocol-derived
settings, a quiet session surface, content-free behavioral telemetry, crash
recovery, and a local-first JSONL sink with optional middleware delivery.

### Added

- A participant-facing TERN sidebar with session state, capture scope, and
  local/mirrored data status.
- Protocol pairing through a copy-safe connection string or `vscode://` deep
  link, with consent shown before any capture starts.
- Session-boundary config refreshes that defer protocol changes until the next
  session instead of mutating a live run.
- A runnable [`examples/tern-lab`](examples/tern-lab) workspace for trying the
  extension without a study server.

### Privacy and reliability

- Capture is local-first: a network outage cannot erase the session file.
- Middleware credentials live in VS Code SecretStorage and are never written
  to event rows.
- The ingest server stamps study identity and assignment keys, while the
  extension records only the content-free fields its protocol enables.
- The extension's core suite covers session timing, pairing, config boundaries,
  telemetry classification, privacy filters, survey state, and sink failure
  isolation.

## [Unreleased]

### Changed

- **Renamed KITE -> TERN** (Telemetry for Engineering & Reasoning Norms).
  Every `kite.*` VS Code setting, command id, context key, and storage key
  is now `tern.*`; the marketplace extension id changes from `kite` to
  `tern`. The protocol schema's `instruments.kite` block is renamed to
  `instruments.tern`, gated behind `protocolVersion: 4` (older protocols
  on v1-v3 keep validating against `kite` unchanged; consumers branch on
  version, never guess). No behavioral change.

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
- **`tern.behavior.*` settings** - per-signal switches and all
  heuristic thresholds; `tern.session.*` provenance fields.

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
