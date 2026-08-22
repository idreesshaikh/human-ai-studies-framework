# TERN - Developer Study Companion

A zero-distraction VS Code extension for developer studies. While a participant
works on a task (with or without AI assistance), it:

- **Samples fatigue in-flow** - a 7-point Likert micro-prompt appears at a
  configurable interval as a native floating QuickPick (the same translucent,
  centered overlay as the command palette). Keyboard-only: `1`–`7` + Enter,
  `Esc` to skip. It **waits for a typing pause** before appearing, so it never
  interrupts mid-keystroke.
- **Detects "stuck" moments** - when the participant dwells on the same code
  region without editing (while still visibly active), or scroll-thrashes back
  and forth re-reading the same area, a soft rectangular border is drawn
  _directly around those lines of code_ with clickable actions above it:
  _Yes, I'm stuck · No, just thinking · I'd like a hint · Dismiss_. Ignored
  prompts time out silently after 60 s.
- **Runs the study session clock** - start a session with a participant ID and
  A/B condition (`ai-assisted` / `unassisted`); a status-bar countdown is the
  only permanent UI. When time is up, a frosted-glass **end-of-study debrief**
  (NASA-TLX-inspired, same 7-point scale) opens automatically. Breaks can be
  **paused and resumed** (excluded from the study clock and the probe
  schedule), and an interrupted session (IDE crash, window reload) is offered
  for **crash recovery** on next launch, with the downtime counted as paused
  time rather than work.
- **Records everything as research-ready JSONL** - one file per session,
  optionally mirrored to the team's Python middleware over HTTP.

This extension hosts two of the framework's instrument legs (decision D12:
one install, one sink pipeline): the _cognitive/self-report_ leg above, and
the **behavioral telemetry** leg - tab/file focus switches, visible-range
(scroll) tracking, edit bursts with origin classification (human / AI /
paste / undo-redo), clipboard-paste sizes, the AI-completion lifecycle with
review latency, save events, and active/idle heartbeats (see the event table
below and `docs/adaptation-notes.md`). It complements the static code
metrics pipeline (`../metrics/` in this repository - see the
[root README](../README.md)). All legs share one timeline via the join keys
and the middleware.

> Working on the extension itself? See `PROJECT_GUIDE.md` for architecture, the
> dev workflow, the event schema, and porting notes.

---

## Quick start

```bash
npm install
npm run compile
```

Open this folder in VS Code and press **F5** → an Extension Development Host
window opens with the extension loaded. In that window:

1. Click **`Study: idle`** in the status bar (or run
   _TERN: Start Study Session_ from the command palette).
2. Enter a participant ID (e.g. `P07`) and pick the condition.
3. Work normally. The countdown runs in the status bar; fatigue prompts appear
   every 15 min (default); stuck prompts appear inline when the heuristics fire.
4. When the timer elapses (or you run _End Study Session_), the debrief survey
   opens and the data file is finalized.

To install for real participants: `npm run package` produces a `.vsix`, then
`code --install-extension tern-0.2.0.vsix`.

To try the stuck prompt quickly, set `tern.stuck.thresholdSeconds`
to `15` and `tern.stuck.cooldownMinutes` to `1`, start a session,
place the cursor in a file and wiggle it occasionally without typing.

### Connecting to a study (participant enrollment)

The Quick start above configures the extension by hand, which is ideal for
local testing. Real participants instead **connect to a study on the
middleware**, so their identity, condition, and capture settings all come
from the study protocol — no manual configuration, no side-channel.

1. The researcher mints a **connection string** for the participant (from the
   platform / middleware). It looks like `https://your-study-server#<token>`.
2. In VS Code, run **_TERN: Connect to Study_** from the command palette and
   paste the connection string. (A `vscode://…/pair?c=<connection-string>`
   deep link runs the same flow.)
3. The extension shows the study's **consent statement**; capture begins only
   after the participant explicitly accepts.
4. On accept, the extension fills in the participant ID, condition, study ID,
   and the middleware endpoint automatically, and stores a session credential
   securely (VS Code SecretStorage). A one-line summary confirms exactly what
   the study will capture.
5. Run **_TERN: Start Study Session_** when ready — the session uses the
   configuration that arrived from the study.

The middleware refuses to pair a study with no compiled, validated protocol —
there is no separate ethics-approval gate; that approval is the university's
to grant, and what the platform owes the participant is the consent statement
above, shown before capture begins. Capture settings are re-checked at the
start of each session, so a researcher can update the protocol between
sessions and paired participants pick up the change on their next start.

### Development

```bash
npm run compile     # build the extension to out/
npm run typecheck   # strict type-check, no emit
npm test            # compile + run the core unit suite (node:test)
```

The portable core (`src/core/*` - session clock, stuck heuristics, recorder,
sinks) is covered by a fast, dependency-free unit suite under `test/`, using
Node's built-in test runner with mocked timers so the time-based logic (probe
schedules, dwell/thrash thresholds, pause accounting) is exercised
deterministically without launching an IDE.

---

## Data

Events land in `<workspace>/.study-data/<participant>_<timestamp>.jsonl`
(configurable). Every line is one event:

```json
{
  "ts": "2026-07-07T14:03:22.114Z",
  "sessionId": "s-lx2...",
  "participantId": "P07",
  "condition": "ai-assisted",
  "seq": 12,
  "type": "fatigue_response",
  "payload": {
    "trigger": "scheduled",
    "value": 4,
    "skipped": false,
    "msToAnswer": 2310,
    "minutesIntoSession": 15
  }
}
```

| Event type                                   | When                             | Key payload fields                                                                |
| -------------------------------------------- | -------------------------------- | --------------------------------------------------------------------------------- |
| `session_start`                              | Session begins                   | plannedDurationMin, ide, ideVersion, platform, workspace                          |
| `fatigue_prompt_shown`                       | Likert probe rendered            | trigger (`scheduled`/`manual`)                                                    |
| `fatigue_response`                           | Probe answered/skipped           | value (1–7 or null), msToAnswer, minutesIntoSession                               |
| `stuck_detected`                             | Heuristic fired                  | file, startLine, endLine, reason (`dwell`/`scroll-thrash`), evidenceMs            |
| `stuck_response`                             | Participant reacted              | answer (`yes`/`no`/`hint`/`dismissed`/`timeout`), msToAnswer, region              |
| `hint_requested`                             | "I'd like a hint" clicked        | region                                                                            |
| `session_paused` / `session_resumed`         | Break started / ended            | minutesIntoSession, thisPauseMs, totalPausedMs, cause (`manual`/`crash-recovery`) |
| `window_blur` / `window_focus`               | IDE lost / regained focus        | awayMs, minutesIntoSession                                                        |
| `post_prompt_resumption`                     | First edit after a prompt closed | promptType, lagMs                                                                 |
| `session_timer_ended`                        | Clock elapsed / manual end       | reason, actualDurationMs, pausedMs                                                |
| `end_survey_response` / `end_survey_skipped` | Debrief submitted / dismissed    | responses (per-item 1–7), comments, msToComplete                                  |
| `session_end`                                | Everything flushed               | reason                                                                            |

### Behavioral telemetry events (schema v3)

The behavioral leg (MP-05) adds the event types below. All payloads are
FR-ETH-2-safe: sizes, shapes, and timings only - never code content,
keystrokes, clipboard text, or off-workspace paths. Capture is filtered to
protocol-declared languages (`tern.behavior.languages`, pilot:
Python) and workspace-internal files.

| Event type             | When                                                                           | Key payload fields                                                                                                                                                         |
| ---------------------- | ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `editor_focus`         | Active editor changed (debounced 250 ms: first + last) or window focus changed | file (workspace-relative or `external`), languageId, groupCount - or state (`focused`/`blurred`)                                                                           |
| `visible_range`        | Scroll/resize settled (500 ms per editor)                                      | file, topLine, bottomLine, totalLines - feeds scroll coverage (FR-INST-9)                                                                                                  |
| `edit_burst`           | 2 s without edits, or file switch                                              | file, charsAdded, charsDeleted, linesTouched, durationMs, origin (`human`/`ai`/`paste`/`undo-redo`, FR-INST-10)                                                            |
| `clipboard_paste`      | Paste landed in a captured file                                                | charCount, lineCount, msSinceInternalCopy (present only when the copy happened in-workspace this session), targetFile - content is never read from the clipboard           |
| `ai_suggestion`        | Inline suggestion decision                                                     | suggestionId, action (`shown`/`accepted`/`rejected`/`dismissed`), visibleMs (review latency, FR-INST-8), charCount, lineCount                                              |
| `file_save`            | Captured file saved                                                            | file, charCount, lineCount                                                                                                                                                 |
| `heartbeat`            | Active/idle transition only (never periodic)                                   | state (`active`/`idle`) - active = interaction within a rolling 120 s window (FR-INST-11)                                                                                  |
| `attention`            | Caret/hover left a line-region band, or file switch                            | file, startLine, endLine, focusMs, cursorMs, hoverMs, edited, mode (`reading`/`editing`/`mixed`), exitReason - region-level time-on-code, present-gated (idle/blur paused) |
| `environment_snapshot` | Once at session start                                                          | vscodeVersion, extensionVersions, os, agentTool, agentModelId, taskId (FR-INST-14 replication provenance)                                                                  |

Set `tern.output.httpEndpoint` (e.g.
`http://127.0.0.1:8000/ingest/events`) to also stream batched events to the
middleware - same decoupled "lightweight sensor → local daemon" architecture
as ActivityWatch. The JSONL file is always written regardless, so a dead
server never loses data. Batches POST as
`{"source":"cognitive-overlay","events":[...]}` every 5 s.

If a capture leg looks empty, events aren't reaching the middleware, or a
prompt never fires, see [`docs/troubleshooting.md`](docs/troubleshooting.md).

---

## How stuck detection works

Two heuristics, both requiring the participant to be _demonstrably active_
(without eye tracking, perfectly motionless staring is indistinguishable from
being away from the keyboard, so faint activity - cursor moves, scrolling,
focus - is required before anything is classified as "stuck" rather than
"idle"):

1. **Dwell** - the cursor stays within ±6 lines of the same spot, signals keep
   arriving, but no edits happen for `thresholdSeconds` (default 90 s).
2. **Scroll-thrash** - the visible range reverses direction ≥4 times within a
   minute over a span of <200 lines: re-reading the same code without progress.

Both share a cooldown (default 5 min), pause while any prompt is on screen,
and are suppressed when the window loses focus. All thresholds are settings
under `tern.stuck.*`; restrict detection to certain languages with
`tern.stuck.languages` (e.g. `["python"]` for the first study
stage).

The heuristics live in pure TypeScript (`src/core/stuckDetector.ts`) and can
be tuned and unit-tested without launching an IDE.

---

## Architecture & porting to other IDEs

```
src/
├─ core/                 PORTABLE - zero IDE imports
│  ├─ types.ts           Event schema, EditorSignal, EventSink, StuckRegion
│  ├─ stuckDetector.ts   Dwell + scroll-thrash heuristics (pure logic)
│  ├─ session.ts         Study clock: duration, fatigue schedule, ticks
│  ├─ surveys.ts         Likert instruments (fatigue probe, TLX-style debrief)
│  └─ recorder.ts        Stamps events with session meta + sequence numbers
└─ vscode/               ADAPTER - everything VS Code-specific
   ├─ signals.ts         Native events → EditorSignal (the whole sensor surface)
   ├─ stuckPrompt.ts     Border decoration + CodeLens actions on the code
   ├─ fatiguePrompt.ts   Likert as floating QuickPick
   ├─ endSurvey.ts       Glassmorphic debrief webview
   ├─ statusBar.ts       Countdown + session menu
   ├─ sinks.ts           JSONL file + batching HTTP sink
   └─ extension.ts       Wiring & commands
```

The core never imports `vscode`. An adapter owes the core exactly four things:

| Contract                | VS Code implementation                                         | JetBrains equivalent                                                                        |
| ----------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Feed `EditorSignal`s    | selection/visibleRanges/document-change/window-state listeners | `CaretListener`, `VisibleAreaListener`, `DocumentListener`, `ApplicationActivationListener` |
| Render the stuck prompt | `TextEditorDecorationType` border + CodeLens                   | `RangeHighlighter` + inlay hint / editor banner                                             |
| Render Likert prompts   | QuickPick / webview                                            | popup (`JBPopupFactory`) / dialog                                                           |
| Provide an `EventSink`  | Node `fs` + `fetch`                                            | `java.nio` + HTTP client                                                                    |

So a JetBrains (PyCharm/IntelliJ) port is a Kotlin re-implementation of the
adapter column only; the heuristics, schedules, event schema, and survey
wording stay identical - which is exactly what you want for cross-IDE
comparability in the study.

## Design decisions worth knowing

- **Why QuickPick and not a floating panel?** VS Code deliberately has no
  arbitrary-overlay API. QuickPick _is_ the platform's native floating glass
  surface - themed, centered, keyboard-first, instantly dismissible - and
  using it means zero fighting with the renderer and no risk of blocking the
  editor.
- **Prompts defer to flow.** Scheduled fatigue prompts wait for ≥4 s of typing
  silence (up to 60 s) before appearing. Stuck prompts never steal focus at
  all - they are painted _around_ the code and answered by mouse or left to
  time out (the timeout itself is recorded, which is signal too).
- **One prompt at a time, everywhere.** Any visible prompt suppresses stuck
  detection, and every prompt interaction resets the detector cooldown.
- **Timestamps + participant + condition on every row** make it trivial to
  join this dataset with the behavior-capture stream and the static-metrics
  snapshots in pandas.
