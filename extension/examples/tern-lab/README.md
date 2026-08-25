# TERN lab

This is a deliberately small, dependency-free workspace for trying TERN
without connecting to a real study. It gives the extension enough surface area
to make the important signals visible: focus changes, scrolling, edits, saves,
idle/active transitions, and the stuck heuristic.

## Open it

From the repository root:

```bash
code --extensionDevelopmentPath=extension extension/examples/tern-lab
```

Or open the folder in VS Code after installing the `.vsix` from the release.
The workspace settings are a standalone local-only preset. A PHOENIX-linked
session can replace its duration, task, condition, endpoint, and capture scope
at pairing/session start, so inspect the pre-flight rather than assuming these
local defaults apply. The feature-rich linked rehearsal is documented in the
[local PHOENIX + TERN demo runbook](../../../docs/demo-runbook.md).

## Try the extension

1. Open `sample_app.py`.
2. Run **TERN: Start Study Session**, use `DEMO-01`, choose **Unassisted**,
   and accept the pre-flight summary.
3. Move between `sample_app.py` and this README, scroll through the file, make
   a small edit, and save. These actions produce content-free telemetry.
4. To see stuck detection, put the cursor in `prioritize_tasks`, keep the
   editor focused, and move the caret within the same small region without
   typing. After about 15 seconds, TERN draws its inline prompt above the code.
5. Click the status-bar timer to open the session menu. Use **Log fatigue now**
   for an immediate 1–7 probe, or **End study session** to open the debrief.

The resulting JSONL file is written to `.study-data/` inside this workspace.
It contains counts, timings, line ranges, and event types—not code, keystrokes,
or clipboard text.

## Run the sample

The file uses only Python's standard library:

```bash
python sample_app.py
```

The slow-looking `prioritize_tasks` loop is intentional: it is an easy place
to pause and observe TERN without needing a broken program or a real task.
