# Privacy

TERN records when and how much you edit, scroll, paste and switch files, and
your answers to the study's questions. It does not record your keystrokes, the
code you write, or what you copy. This page lists what it does record,
including the few events that contain text or names.

## Never recorded

- **Keystrokes.**
- **The text of your code.** Edit events carry character and line counts.
- **Clipboard text.** When you copy in the editor, TERN keeps a salted hash of
  the copied text in memory for up to 30 minutes, so it can tell whether a
  later paste came from inside the editor. The hash is never written to a file.
- **Error and warning messages.** `ide_health` carries counts only.

## Recorded

- **Activity:** which file is open, which lines are visible, the size of each
  edit and paste, saves, whether you are active or idle, how long you stay on a
  region of lines, and inline suggestions you accept or dismiss.
- **Answers:** fatigue ratings, answers to the stuck prompt, and the study's
  questionnaires.
- **The session:** the clock, breaks, and when VS Code gains or loses focus.

The [Captured data](captured-data.md) page lists every event and field.

## Text and names in the data

| What | Recorded in |
| --- | --- |
| Text you type in answers: closing comments, comprehension answers, the model name | `end_survey_response`, `comprehension_probe_response`, `environment_snapshot` |
| File names and paths relative to the workspace | `editor_focus`, `visible_range`, `edit_burst`, `file_save`, `attention` |
| The full path on disk, which includes your user name, even for files outside the workspace | `stuck_detected`, `stuck_response`, `hint_requested` |
| The workspace folder name | `session_start` |
| IDs and versions of installed AI-assistant extensions | `environment_snapshot` |
| A value you tried to set while connected to a study | `settings_override_attempt` |
| The error text when one of TERN's own sensors fails | `behavior_sensor_error` |

A study can also use instruments other than TERN, and some of them can store
code. When one does, the **What is captured** view says
**This study stores code**.

## Where the data goes

1. **Your computer.** Every session writes one file, always, even without a
   network. See [where the file is](captured-data.md#where-the-file-is).
2. **The study server**, when you are connected to a study. Events are sent
   every 5 seconds to the address in your study link. With an `http://`
   address they travel unencrypted.

## Delete your data

TERN never deletes event files, including when you disconnect from a study.
To remove them, delete the `study-data` folder yourself. A study's task folder,
if TERN downloaded one, is in `study-workspaces` in the same place. Events
already sent to the study server stay there; ask the researcher to remove them.

## Consent

When you connect to a study, TERN shows the study's consent statement and
records nothing until you choose **I consent**. PHOENIX writes that statement
from the study's protocol.

- The study can change what it captures between your sessions. TERN applies
  the current settings at the start of each session and does not ask for
  consent again.
- The summary before each session shows the main kinds of editor activity
  that are on or off. It is not a complete list: questions, window focus,
  saves, the environment snapshot and diagnostic counts are recorded without
  appearing in it. This page and [Captured data](captured-data.md) are the
  complete list.
- Sessions that are not connected to a study show no consent statement. Use
  them only for testing.

## If VS Code crashes

Events written before the crash stay in the file, but the last few may be lost
or cut off. Events that were not yet sent to the study server are not sent
later. When you recover the session, the time VS Code was closed counts as a
break. TERN does not add events for that time.
