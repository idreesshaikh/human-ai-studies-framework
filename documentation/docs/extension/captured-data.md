# Captured data

TERN writes one JSONL file per session, named `<participant>_<start time>.jsonl`.
Each line is one event. This page lists where the file is, what every event
carries and how events reach the study server. Researchers use it to know what the
data can and cannot show.

## Where the file is

| Session | Folder |
| --- | --- |
| Paired | `study-data/` in VS Code's storage for the extension. This cannot be changed. |
| Unpaired | `tern.output.directory` if set, otherwise `.study-data/` in the workspace, otherwise VS Code's storage for the extension |

VS Code's storage for the extension is in your VS Code user folder:

=== "macOS"

    `~/Library/Application Support/Code/User/globalStorage/idreesrazak.tern/study-data/`

=== "Windows"

    `%APPDATA%\Code\User\globalStorage\idreesrazak.tern\study-data\`

=== "Linux"

    `~/.config/Code/User/globalStorage/idreesrazak.tern/study-data/`

## One event

Every event has the same envelope. `seq` counts up from 0 within a session, and
`mono` is milliseconds since the session started on a clock that system time
changes do not affect.

```json
{
  "v": 6,
  "ts": "2026-07-07T14:03:22.114Z",
  "mono": 901554,
  "sessionId": "s-lx2...",
  "participantId": "P07",
  "condition": "ai-assisted",
  "taskId": "",
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

## Session and answers

| Event | When | Main payload fields |
| --- | --- | --- |
| `session_start` | Session begins | plannedDurationMin, ide, ideVersion, platform, workspace |
| `pre_task_covariate` | A question before the task is answered | Depends on the questionnaire |
| `fatigue_prompt_shown` | Fatigue question appears | trigger (`scheduled` or `manual`), deferralMs |
| `fatigue_prompt_interrupted` | A shown fatigue question closes because of a break or the session menu | trigger, reason, deferralMs, minutesIntoSession |
| `fatigue_response` | Fatigue question answered or skipped | value (1 to 7, or null), skipped, cancelled, msToAnswer, minutesIntoSession, scaleId, points, deferralMs |
| `stuck_detected` | Stuck prompt appears | file, startLine, endLine, reason (`dwell` or `scroll-thrash`), evidenceMs |
| `stuck_response` | Stuck prompt answered or timed out | answer (`yes`, `no`, `hint`, `dismissed` or `timeout`), msToAnswer, region |
| `hint_requested` | **I'd like a hint** chosen | region |
| `session_paused` | Break starts | minutesIntoSession |
| `session_resumed` | Break ends, or a session is recovered | cause (`manual` or `crash-recovery`), totalPausedMs, thisPauseMs or downtimeMs |
| `window_blur` / `window_focus` | VS Code loses or regains focus | awayMs, minutesIntoSession |
| `post_prompt_resumption` | First edit after a prompt closes | promptType, lagMs |
| `settings_override_attempt` | A `tern.*` setting is changed in a paired session | key, lockedValue, attemptedValue |
| `session_timer_ended` | Clock runs out, or the session is ended | reason, actualDurationMs, pausedMs |
| `survey_response` / `survey_skipped` | Closing questionnaire, protocol version 6 and later | Depends on the questionnaire |
| `end_survey_response` / `end_survey_skipped` | Closing questions, earlier protocols | responses (1 to 7 per item), comments, msToComplete |
| `session_end` | Everything is written | reason |

`stuck_detected` stores `file` as the full path on disk, which includes your
user name. `stuck_response` and `hint_requested` repeat it in `region`. Other
events use paths relative to the workspace.

## Editor activity

These events come from the editor activity part of TERN, which the protocol
can switch on and off per kind. Unless noted, they cover only files in the
workspace in the languages listed in `tern.behavior.languages`.

| Event | When | Main payload fields |
| --- | --- | --- |
| `editor_focus` | Active editor or window focus changes | file, languageId, groupCount, or state (`focused` or `blurred`). Any language; files outside the workspace are recorded as `external` |
| `visible_range` | Scrolling settles | file, topLine, bottomLine, totalLines |
| `edit_burst` | 2 seconds pass without an edit, or you switch file | file, charsAdded, charsDeleted, linesTouched, durationMs, origin |
| `clipboard_paste` | A paste lands in a recorded file | charCount, lineCount, msSinceInternalCopy, targetFile |
| `ai_suggestion` | An inline suggestion is accepted or dismissed with the keyboard | suggestionId, action, and for accepted suggestions charCount and lineCount |
| `file_save` | A recorded file is saved | file, charCount, lineCount |
| `heartbeat` | You become active or idle | state (`active` or `idle`) |
| `attention` | Caret or mouse leaves a region of lines | file, startLine, endLine, focusMs, cursorMs, hoverMs, edited, mode, exitReason |
| `environment_snapshot` | Once, at session start | See below |
| `ide_health` | Diagnostic counts change | errorCount, warningCount, buildInvocations, testInvocations |
| `behavior_sensor_error` | One of TERN's sensors fails | source, message |
| `comprehension_probe_response` | A comprehension question is answered or expires. Off by default | chunkRef, promptKind, answer, correct, msToAnswer, expired |

Notes on reading these fields:

- **`origin` on `edit_burst`** is `ai` when the edit came within 500 ms of an
  accepted inline suggestion, or added 80 or more characters in under 50 ms.
  Formatters, snippets and renames can produce the same pattern and its error
  rates have not been measured, so it is not evidence of AI use.
- **`ai_suggestion`** records the **Tab** and **Esc** keys on an inline
  suggestion from any provider. VS Code does not report whether a suggestion
  was shown, so suggestions that were ignored are not recorded.
- **`ide_health`** counts errors and warnings across the whole IDE, not one
  file, and only for windows where a count was above zero. In this version
  `buildInvocations` and `testInvocations` are always 0.
- **`environment_snapshot`** records the VS Code version, the operating system,
  the tool and model the study declared, the model name you entered, which
  editor activity is captured, and the IDs and versions of installed extensions
  whose names match common AI assistants (Copilot, Claude, Codeium, Cursor,
  Tabnine, Continue, Cody, Supermaven, Windsurf). An installed extension is not
  evidence that it was used.

## Sending events to the study server

The file is always written first, so a server that is down does not stop a
session. When a session is paired, or when `tern.output.httpEndpoint` is set,
TERN also sends events to the server every 5 seconds:

```http
POST /ingest/events
{"source": "tern", "events": [...]}
```

- Events that have not been sent yet are held in memory, up to 2,000. When
  that fills, the oldest are dropped.
- Each request times out after 4 seconds, and TERN waits longer between
  attempts after 3 failures.
- After a crash, events that were never sent are not sent later. They are still
  in the file.

!!! note "Checking delivery"
    In a paired session the **Your data** view shows when events were last sent
    and how many are not yet sent. Researchers can also check the event rate and
    gaps for each running session on the PHOENIX **Run** tab.

## Next steps

- [Privacy](privacy.md) lists the few events that contain text or names
- Researchers: [Review sessions and export](../platform/data.md)
