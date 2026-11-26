# About TERN

TERN is the VS Code extension participants run during a study. It times the
session, asks the study's short questions, and records editor activity as one
JSONL event file per session. It does not record keystrokes or the code
participants write. Participants install it once and connect it with the link the
researcher sends.

This guide describes TERN as it is in the repository, listed in the VS Code
Extensions view as **StudyLoop Capture**. The `v1.0.1` release differs from the
current source; see [Install and connect](install.md).

## Paired and unpaired sessions

A participant connects TERN to a study with the link the researcher sends from
PHOENIX. Everything else follows from whether that connection exists.

=== "Paired with a study"

    - The study configuration controls capture. During a paired session,
      changes to locked settings do not change capture and are recorded as
      `settings_override_attempt`; TERN also attempts to restore the settings.
    - The server assigns the condition. TERN never shows it to the participant.
    - Events are written to VS Code's own storage for the extension and sent
      to the study server in batches.
    - The participant reads the study's consent statement and chooses
      **I consent** before any session can start.

=== "Unpaired"

    - For trying TERN and for development. TERN reads the `tern.*` settings.
    - Each session asks for a participant ID and a condition.
    - Events are written to a local folder. They are sent to a server only if
      `tern.output.httpEndpoint` is set.
    - No consent statement is shown.

## What participants see

| Where | What it shows |
| --- | --- |
| Status bar | `Study: idle`, then the countdown (`42:10`), `42:10 paused` during a break, and `Study: debrief` at the end. Click it to open the session menu. |
| **StudyLoop study** sidebar | Three views: **Session**, **What is captured** and **Your data**. |
| Prompts | The fatigue question, the stuck prompt on the code, and the questions at the start and end of a session. |

[Run a session](using.md) walks through each of these.

## Where the data comes from

TERN is one of several instruments a study can use. Each writes its own events,
and PHOENIX joins them by session.

| Instrument | Records | Set up by |
| --- | --- | --- |
| TERN prompts | Fatigue ratings, stuck responses, questionnaires | The protocol |
| TERN editor activity | Focus switches, scroll ranges, edit sizes, paste sizes, accepted or dismissed inline suggestions, saves, idle time | The protocol |
| agent-capture | Agent sessions, turns, tool calls, workspace snapshots, commits and task outcomes from Claude Code | Hooks the researcher installs |
| Code metrics | Structural measures of the Python code a participant produced | The researcher, after the session |

!!! note "Signals are not proof of AI use"
    An edit marked `origin: ai` arrived within 500 ms of an accepted inline
    suggestion, or added 80 or more characters in under 50 ms. Formatters,
    snippets and renames can produce the same pattern, and the error rates of
    these signals have not been measured. TERN cannot show that a participant in
    a no-AI condition used no AI, and a missing signal does not show that no AI
    was used.

## Prompts wait for the participant

- A scheduled fatigue question waits for 4 seconds without typing, up to 60
  seconds, before it appears.
- The stuck prompt never takes keyboard focus. It closes itself after 60
  seconds, and that timeout is recorded too.
- No fatigue question appears in the last 5 minutes of a session.

## Try it without a study

The repository includes [`extension/examples/tern-lab`](https://github.com/idreesshaikh/human-ai-studies-framework/tree/main/extension/examples/tern-lab),
an unpaired workspace that writes only to a local folder. It sets a 15-minute
session and a 15-second stuck threshold. Open `sample_app.py`, start a session,
make a few edits, then stay on `prioritize_tasks` without typing to see the
stuck prompt.

Unpaired sessions read the `tern.*` settings. Paired sessions use the study's
locked configuration instead. These are the settings you are most likely to
change for an unpaired session:

| Setting | Default | What it does |
| --- | --- | --- |
| `tern.session.durationMinutes` | `60` | Session length |
| `tern.fatigue.intervalMinutes` | `15` | Time between fatigue questions, varied by ±20% |
| `tern.fatigue.quietTailMinutes` | `5` | No fatigue questions in this final stretch |
| `tern.stuck.enabled` | `true` | Show the stuck prompt |
| `tern.stuck.thresholdSeconds` | `90` | Time on one region without editing before the prompt appears |
| `tern.stuck.cooldownMinutes` | `5` | Minimum time between stuck prompts |
| `tern.behavior.enabled` | `true` | Record editor activity |
| `tern.behavior.languages` | `["python"]` | Languages whose files are recorded. Empty means all |
| `tern.output.directory` | empty | Folder for event files. Empty means `.study-data/` in the workspace |
| `tern.output.httpEndpoint` | empty | Also send events to this server, for example `http://127.0.0.1:8000/ingest/events` |

All 45 settings, with descriptions, are in the **Settings** editor under
*StudyLoop Capture*.

## Next steps

- [Install and connect](install.md)
- [Run a session](using.md)
- [Captured data](captured-data.md) and [Privacy](privacy.md)
- Researchers: [Give participants TERN](../platform/give-participants-tern.md)
