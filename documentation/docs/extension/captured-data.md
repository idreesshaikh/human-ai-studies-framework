# Captured data

Everything TERN records lands in one file per session:
`<workspace>/.study-data/<participant>_<timestamp>.jsonl` (configurable).
Every line is one event, stamped with the session, participant, condition, and
a sequence number  -  so this dataset joins cleanly with the behavior-capture
stream and the static-metrics snapshots in pandas.

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

## Cognitive / self-report events

| Event type | When | Key payload fields |
| --- | --- | --- |
| `session_start` | Session begins | plannedDurationMin, ide, ideVersion, platform, workspace |
| `fatigue_prompt_shown` | Likert probe rendered | trigger (`scheduled`/`manual`) |
| `fatigue_response` | Probe answered/skipped | value (1–7 or null), msToAnswer, minutesIntoSession |
| `stuck_detected` | Heuristic fired | file, startLine, endLine, reason (`dwell`/`scroll-thrash`), evidenceMs |
| `stuck_response` | Participant reacted | answer (`yes`/`no`/`hint`/`dismissed`/`timeout`), msToAnswer, region |
| `hint_requested` | "I'd like a hint" clicked | region |
| `session_paused` / `session_resumed` | Break started / ended | minutesIntoSession, thisPauseMs, totalPausedMs, cause |
| `window_blur` / `window_focus` | IDE lost / regained focus | awayMs, minutesIntoSession |
| `post_prompt_resumption` | First edit after a prompt closed | promptType, lagMs |
| `session_timer_ended` | Clock elapsed / manual end | reason, actualDurationMs, pausedMs |
| `end_survey_response` / `end_survey_skipped` | Debrief submitted / dismissed | responses (per-item 1–7), comments, msToComplete |
| `session_end` | Everything flushed | reason |

## Behavioral telemetry events (schema v4)

The behavioral leg adds the event types below. All payloads are
FR-ETH-2-safe: sizes, shapes, and timings only  -  never code content,
keystrokes, clipboard text, or off-workspace paths. Capture is filtered to
protocol-declared languages (`tern.behavior.languages`, pilot: Python) and
workspace-internal files.

| Event type | When | Key payload fields |
| --- | --- | --- |
| `editor_focus` | Active editor changed or window focus changed | file, languageId, groupCount  -  or state (`focused`/`blurred`) |
| `visible_range` | Scroll/resize settled | file, topLine, bottomLine, totalLines |
| `edit_burst` | 2 s without edits, or file switch | file, charsAdded, charsDeleted, linesTouched, durationMs, origin |
| `clipboard_paste` | Paste landed in a captured file | charCount, lineCount, msSinceInternalCopy, targetFile |
| `ai_suggestion` | Inline suggestion decision | suggestionId, action (`shown`/`accepted`/`rejected`/`dismissed`), visibleMs, charCount, lineCount |
| `file_save` | Captured file saved | file, charCount, lineCount |
| `heartbeat` | Active/idle transition only | state (`active`/`idle`) |
| `attention` | Caret/hover left a line-region band, or file switch | file, startLine, endLine, focusMs, cursorMs, hoverMs, edited, mode, exitReason |
| `environment_snapshot` | Once at session start | vscodeVersion, extensionVersions, os, agentTool, agentModelId, taskId |
| `ide_health` | After a diagnostics/build/test count changes | errorCount, warningCount, buildInvocations, testInvocations |
| `behavior_sensor_error` | A behavioral sensor throws | source, message |
| `comprehension_probe_response` | A comprehension probe is answered or expires | chunkRef, promptKind, answer, correct, msToAnswer, expired |

## Sinks

The JSONL file is always written regardless  -  a dead server never loses data.
Set `tern.output.httpEndpoint` (e.g. `http://localhost:8000/cognitive`) to also
stream batched events to the middleware. Batches POST as
`{"source":"tern","events":[...]}` every 5 s; the source string is normalised
on ingest, so an older editor's events still join the same stream.