# Project Guide - Cognitive Overlay

A deep reference for developing, testing, and maintaining this VS Code
extension. For a participant/facilitator-facing overview, see
[`README.md`](./README.md); this document is for people working _on_ the code.

---

## 1. What this is

Cognitive Overlay hosts the **cognitive / self-report leg** and the
**behavioral telemetry leg** of the developer-study framework (decision D12:
one extension, one sink pipeline). It runs inside a participant's editor
while they complete a task (with or without AI assistance) and captures:

- **Fatigue** - periodic single-item Likert probes, timed into typing pauses.
- **Stuck moments** - inline prompts driven by dwell / scroll-thrash heuristics.
- **Session structure** - a pausable, crash-resumable study clock plus an
  end-of-study NASA-TLX-style debrief.
- **Behavior** (MP-05) - focus switches, visible ranges, edit bursts with
  origin classification (human/ai/paste/undo-redo), clipboard-paste sizes,
  the AI-completion lifecycle with review latency, saves, and active/idle
  heartbeats. Mechanisms and their blind spots: `docs/adaptation-notes.md`.

Everything is written to research-ready JSON Lines, one file per session, with
every row carrying `ts` / `participantId` / `condition` so the dataset joins
cleanly with the other legs (static metrics, agent interaction - see the
[repository root README](../README.md)).

Those sibling legs are **not built here**; this folder is _only_ the VS Code
extension.

---

## 2. Architecture at a glance

The single most important rule: **`src/core` never imports `vscode`.**

```
src/
├─ core/                 PORTABLE - pure TypeScript, zero IDE imports
│  ├─ types.ts           Event schema (SCHEMA_VERSION), EditorSignal, EventSink
│  ├─ session.ts         Study clock: duration, fatigue schedule, pause/resume
│  ├─ stuckDetector.ts   Dwell + scroll-thrash heuristics (pure logic)
│  ├─ surveys.ts         Likert instruments (fatigue probe + TLX-style debrief)
│  ├─ recorder.ts        Stamps events with session meta + sequence numbers
│  ├─ behavior.ts        Edit-burst aggregator + origin classifier (MP-05)
│  ├─ idle.ts            Active/idle rolling-window state machine (MP-05)
│  ├─ captureFilter.ts   Language / workspace-internal capture predicate
│  └─ debounce.ts        First+last and trailing debouncers for hot signals
└─ vscode/               ADAPTER - everything VS Code-specific
   ├─ signals.ts         Native events → EditorSignal (stuck detection feed)
   ├─ behavior.ts        Behavioral telemetry sensors + wrapper commands
   ├─ stuckPrompt.ts     Border decoration + CodeLens actions on the code
   ├─ fatiguePrompt.ts   Likert rendered as a floating QuickPick
   ├─ endSurvey.ts       Glassmorphic debrief webview
   ├─ statusBar.ts       Countdown + session menu
   ├─ sinks.ts           JSONL file + batching HTTP sink
   └─ extension.ts       Activation, commands, and wiring
```

**Why the split?** The heuristics, schedules, event schema, and survey wording
are the scientifically meaningful parts and must stay identical across IDEs for
cross-tool comparability. Keeping them free of `vscode` imports means they are
unit-testable without launching an editor, and a JetBrains port re-implements
only the `src/vscode` column (see §7).

### Data flow

```
VS Code events ──▶ signals.ts ──▶ StuckDetector (core)
                                     │ onStuck(region)
                                     ▼
                              stuckPrompt.ts (inline UI)
StudySession (core clock) ──▶ onFatigueDue ──▶ fatiguePrompt.ts
        every interaction ──▶ Recorder.record(type, payload)
                                     ▼
                          CompositeSink ──▶ JsonlSink (source of truth)
                                        └──▶ HttpSink (best-effort mirror)
```

---

## 3. Repository layout

| Path                 | Purpose                                              |
| -------------------- | ---------------------------------------------------- |
| `src/core/`          | Portable, IDE-agnostic logic                         |
| `src/vscode/`        | VS Code adapter and extension entry point            |
| `test/`              | `node:test` unit tests for the core + sinks          |
| `out/`               | Compiled extension (git-ignored, built by `compile`) |
| `out-tests/`         | Compiled tests (git-ignored, built by `pretest`)     |
| `.vscode/`           | Launch config, build task, extension recommendations |
| `tsconfig.json`      | Extension build (`src` → `out`, CommonJS)            |
| `tsconfig.test.json` | Test build (`src/core` + `test` → `out-tests`)       |
| `eslint.config.mjs`  | Flat ESLint config (typescript-eslint)               |
| `.prettierrc.json`   | Formatting rules                                     |

---

## 4. Development workflow

### Prerequisites

- **Node.js ≥ 20** (built and tested on Node 22)
- **VS Code ≥ 1.85**

### Setup

```bash
npm install
```

### Run the extension

Press **F5** in VS Code (or run the _"Run Cognitive Overlay Extension"_ launch
config). This compiles via the `npm: compile` pre-launch task and opens an
Extension Development Host with the extension loaded. In that window, click
**`Study: idle`** in the status bar to start a session.

To iterate quickly, run `npm run watch` in a terminal and use **Reload Window**
in the dev host after changes.

### The scripts

| Script                 | What it does                                             |
| ---------------------- | -------------------------------------------------------- |
| `npm run compile`      | Build the extension to `out/`                            |
| `npm run watch`        | Incremental rebuild on save                              |
| `npm run typecheck`    | Type-check without emitting                              |
| `npm run lint`         | ESLint over `src` + `test`                               |
| `npm run format`       | Prettier write                                           |
| `npm run format:check` | Prettier verify (used in CI / `check`)                   |
| `npm test`             | Compile tests (`pretest`) then run them with `node:test` |
| `npm run check`        | typecheck + lint + format:check + test (the gate)        |
| `npm run package`      | Produce a `.vsix` via `vsce`                             |
| `npm run clean`        | Remove `out/`, `out-tests/`, and any `.vsix`             |

**Before committing, run `npm run check`.** It is the single command that must
stay green.

### Tests

Tests use Node's built-in runner (`node:test`) with mocked timers, so the
time-based logic (session clock, dwell/thrash heuristics) is verified
deterministically without real waiting. `test/helpers.ts` advances the mocked
clock in 1 s steps to mirror the production tick cadence.

Because the source uses extensionless CommonJS imports, tests are compiled to
`out-tests/` first (the `pretest` step) and then run - this is wired into
`npm test`, so you just run `npm test`.

---

## 5. Configuration reference

All settings live under the `cognitiveOverlay.*` namespace (VS Code Settings →
search "Cognitive Overlay"). Defined in `package.json` under
`contributes.configuration`.

| Setting                           | Default       | Meaning                                                                                         |
| --------------------------------- | ------------- | ----------------------------------------------------------------------------------------------- |
| `participantId`                   | `""`          | Pre-filled participant ID when starting a session                                               |
| `condition`                       | `unspecified` | A/B arm shown as the default                                                                    |
| `session.durationMinutes`         | `60`          | Session length; the debrief opens when it elapses                                               |
| `fatigue.intervalMinutes`         | `15`          | Mean gap between fatigue probes                                                                 |
| `fatigue.waitForPauseSeconds`     | `4`           | Typing-silence required before a scheduled probe shows                                          |
| `fatigue.jitterPercent`           | `20`          | ± randomization of each probe interval (anti-anticipation)                                      |
| `fatigue.quietTailMinutes`        | `5`           | Suppress probes in the final minutes                                                            |
| `stuck.enabled`                   | `true`        | Toggle stuck detection                                                                          |
| `stuck.thresholdSeconds`          | `90`          | Dwell time before a stuck prompt                                                                |
| `stuck.cooldownMinutes`           | `5`           | Minimum gap between stuck prompts                                                               |
| `stuck.languages`                 | `[]`          | Language IDs to watch (empty = all)                                                             |
| `output.directory`                | `""`          | JSONL destination (empty = `<workspace>/.study-data`)                                           |
| `output.httpEndpoint`             | `""`          | Optional middleware POST endpoint (empty = disabled)                                            |
| `session.taskId`                  | `""`          | Protocol task ID for the environment snapshot                                                   |
| `session.agentTool`               | `""`          | AI agent tool (ai-assisted condition), snapshot provenance                                      |
| `session.agentModelId`            | `""`          | AI agent model id, snapshot provenance                                                          |
| `behavior.enabled`                | `true`        | Master switch for the behavioral telemetry leg                                                  |
| `behavior.capture*`               | `true`        | Per-signal switches: Focus, VisibleRanges, EditBursts, Clipboard, AiLifecycle, Saves, Heartbeat |
| `behavior.languages`              | `["python"]`  | Captured language IDs (empty = all) - FR-INST-12                                                |
| `behavior.workspaceInternalOnly`  | `true`        | Only capture files inside the workspace                                                         |
| `behavior.burstGapMs`             | `2000`        | Edit burst closes after this silence                                                            |
| `behavior.aiCorrelationMs`        | `500`         | Accepted-suggestion window => `origin: ai`                                                      |
| `behavior.aiBlockCharThreshold`   | `80`          | Chars within `aiBlockMaxDurationMs` => `origin: ai`                                             |
| `behavior.aiBlockMaxDurationMs`   | `50`          | Window for the block-injection heuristic                                                        |
| `behavior.pasteCorrelationMs`     | `100`         | Paste-signal window => `origin: paste`                                                          |
| `behavior.idleWindowSeconds`      | `120`         | Rolling activity window for heartbeat transitions                                               |
| `behavior.focusDebounceMs`        | `250`         | Editor-focus debounce (first + last)                                                            |
| `behavior.visibleRangeDebounceMs` | `500`         | Per-editor visible-range debounce                                                               |

---

## 6. Event schema

Every recorded row conforms to `StudyEvent` in `src/core/types.ts` and is
stamped by `Recorder`:

```jsonc
{
  "v": 3,                       // SCHEMA_VERSION - bump on shape changes
  "ts": "2026-07-07T14:03:22.114Z", // wall clock, for cross-leg joins
  "mono": 903221,               // monotonic ms since start, for durations
  "sessionId": "s-lx2...",
  "participantId": "P07",
  "condition": "ai-assisted",
  "seq": 12,                    // monotonic per-session, for gap detection
  "type": "fatigue_response",
  "payload": { "value": 4, "msToAnswer": 2310, ... }
}
```

`SCHEMA_VERSION` lives in `src/core/types.ts`. **Bump it whenever the shape or
meaning of a payload field changes** so analysis scripts can branch on version
rather than guessing from file dates. See the README's event table for the
per-`type` payload fields.

---

## 7. Porting to another IDE

An adapter owes the core exactly four contracts. A JetBrains port is a Kotlin
re-implementation of only these:

| Contract                | VS Code implementation                                               |
| ----------------------- | -------------------------------------------------------------------- |
| Feed `EditorSignal`s    | selection / visibleRanges / document-change / window-state listeners |
| Render the stuck prompt | `TextEditorDecorationType` border + CodeLens                         |
| Render Likert prompts   | QuickPick (fatigue) / webview (debrief)                              |
| Provide an `EventSink`  | Node `fs` + `fetch`                                                  |

The heuristics, schedules, event schema, and survey wording in `src/core` are
reused verbatim - that shared core is what makes the cross-IDE data comparable.

---

## 8. Coding conventions

- **The core/adapter boundary is sacred.** If you find yourself wanting to
  `import * as vscode` inside `src/core`, the logic belongs in the adapter, or
  the data it needs should be passed in as a plain value / callback.
- **Data capture is subordinate to the study.** A failing sink must never
  interrupt the participant - see `Recorder` and the sink failure policies in
  `sinks.ts`. Preserve that: swallow, count, and report once; never throw into
  the session.
- **Prompts defer to flow.** Scheduled probes wait for typing silence; stuck
  prompts never steal focus. Keep new UI equally non-intrusive.
- **Formatting and linting are enforced.** Run `npm run check` before pushing.
  Prettier owns formatting; don't hand-format against it.
- **Keep timing testable.** New time-based logic should live in `src/core` and
  be driven by injected config so it can be unit-tested with mocked timers.
