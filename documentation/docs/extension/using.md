# Run a session

A session runs from **Begin session** to the last question at the end. TERN
records events for the whole of it, except the time you spend on a break.

## Start

Click **Study: idle** in the status bar, or run
**StudyLoop: Start Study Session** from the Command Palette.

=== "Paired with a study"

    1. If the study asks questions before the task, answer them now.
    2. If the study records which AI tool you use, TERN asks for the model
       name.
    3. Read the summary and choose **Begin session**.

    The study has already assigned your participant ID and condition, so TERN
    does not ask for them.

=== "Unpaired"

    1. Enter a participant ID, for example `P07`.
    2. Pick a condition: **AI-assisted**, **Unassisted** or **Unspecified**.
    3. Read the summary and choose **Begin session**.

The summary before **Begin session** shows your participant ID, the session
length, and which kinds of activity will and will not be captured. The
complete list is on the [Captured data](captured-data.md) page.

## During the session

The status bar shows the time left. It turns to a warning color when a fatigue
question is due and shows `paused` during a break. Click it to open the session
menu:

| Menu item | What it does |
| --- | --- |
| **Pause session (break)** | Stops the clock and the question schedule. Becomes **Resume session (break over)** |
| **Log fatigue now** | Answer the fatigue question without waiting for it |
| **Open data folder** | Opens the folder with the event file. Unpaired sessions only |
| **End study session** | Ends early and moves to the closing questions |

While a session runs, TERN handles **Copy**, **Cut** and **Paste**, and **Tab**
and **Esc** on inline suggestions. Each still does what it normally does; TERN
notes the size of what was pasted or accepted.

### The fatigue question

Every 15 minutes, varied by up to 20% so it cannot be anticipated, TERN asks how
tired you feel on a 7-point scale. It waits until you have stopped typing for 4
seconds. Press a number from `1` to `7` and ++enter++, or ++esc++ to skip. No
question appears in the last 5 minutes.

### The stuck prompt

If you stay on the same few lines for 90 seconds without editing, or scroll back
and forth over the same area, TERN draws a border around those lines with four
choices:

*Yes, I'm stuck · No, just thinking · I'd like a hint · Dismiss*

The prompt does not take keyboard focus, so you can keep working. If you ignore
it, it closes after 60 seconds.

!!! warning "Hints are not forwarded"
    After **I'd like a hint**, TERN says the study facilitator has been
    notified. In this version the request is only recorded as
    `hint_requested`; nothing in StudyLoop alerts anyone. Researchers who offer
    hints need to watch for them during the session.

## End

The session ends when the clock runs out or when you choose
**End study session**. The status bar shows **Study: debrief** while you answer
the closing questions.

- **Protocol version 6 and later:** the questionnaires the study declares, such
  as the raw NASA-TLX with its own wording and scoring. If the study declares
  none, no questions appear.
- **Earlier protocols:** six questions on a 7-point scale adapted from the
  NASA-TLX, plus a question about reliance on the AI in AI-assisted sessions,
  and an optional comment. This is not the standard NASA-TLX and has no
  validated total score.

## Breaks and interruptions

- Time on a break is left out of the session clock and the question schedule.
- If VS Code closes during a session, TERN offers to recover it the next time
  you open **the same workspace**. The time VS Code was closed counts as a
  break. TERN saves its state every 15 seconds, so up to 15 seconds of work
  before the crash can also be counted as break time.
- If you choose not to recover, the event file is kept as it is, without a
  `session_end` event.
