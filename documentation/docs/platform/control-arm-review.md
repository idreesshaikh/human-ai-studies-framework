# Control-arm session review

**Session review**, on the **Data** tab, lists what TERN captured in the sessions of
your control conditions that points to AI use. It is a prompt for your judgement,
not a verdict. The error rates of its signals have not been measured, and no
outcome verifies that a participant used AI or stayed free of it.

The review covers conditions the protocol declares as control conditions. It never
guesses them from condition names.

## What each outcome means

| Shown as | Meaning |
| --- | --- |
| **Captured AI-use signal** | A rule fired on the captured data: an accepted inline suggestion, or an agent turn or tool call from hooks you installed. It is a reason to look, not proof of AI use |
| **No captured AI-use signal** | No such signal appears in the captured data. AI use outside the capture is still possible, so this never shows that no AI was used |
| **Capture needs review** | Capture coverage, session boundaries or the event sequence were incomplete, so the review abstains |

Provider queries, bulk-edit heuristics and pastes are shown as ambiguous signals
and do not count as evidence: formatters, snippets and renames can produce the
same pattern. The review never excludes a session by itself.

!!! warning "Accuracy not yet measured"
    Under **Capture limits** the review reports its accuracy as **Not measured**.
    Independent scripted calibration sessions, with a person taking each route,
    are required before its sensitivity and specificity can be stated. Until then,
    treat every outcome as a prompt for your own judgement.

## Use the review

1. Open **Session review** on the **Data** tab. A summary line counts the control
   sessions, the ones with captured-use signals, the ones with incomplete capture
   and the ones with no signal captured.
2. Choose **Show sessions**: **Needs review** (the default), **Control
   conditions** or **All sessions**. **Search review sessions** narrows the list.
3. Expand a session to read why it was shown and its signal counts, such as
   accepted inline suggestions, agent turns and tool calls.
4. Record your decision, if you have one, with a reason. See
   [Tag pilots and record decisions](data.md#tag-pilots-and-record-decisions).

Open **Capture limits** to see what the review cannot see: external command-line
agents, drag-and-drop and clipboard tools, activity outside the editor, and the
inline-suggestion routes that keybindings miss.

## Analysing with the review

Use random assignment as the primary comparison. Treat accepted suggestions and
hooked-agent events as a lower bound on captured use, not total exposure. Do not
exclude participants, or describe a control arm as clean, because a session shows
**No captured AI-use signal**. Use self-report and
[Non-compliance sensitivity](non-compliance.md) to describe AI use you could not
observe.

## Next steps

- [TERN's captured data](../extension/captured-data.md) lists every event the review reads
- [Scope and limits](../reference/scope.md)
