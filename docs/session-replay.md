# Replay captured study sessions

In **Data**, expand a session, then choose **Replay session**. Use Previous/Next,
Play/Pause, or the keyboard-operable position slider. Frames are ordered by
timestamp, then source and sequence; wall timestamps are normalized for offsets.
Playback is an inspection stepper, not a reconstruction of real-time keystrokes.
Integrity flags remain visible. Reload failures have an explicit retry.

Replay reads only events attributed to the selected study, requires view access,
and refuses more than 10,000 frames rather than silently showing a complete-looking
partial replay. Large sessions remain available through the scoped study export.

Default capture contains code-change **counts**, not code text. The replay says
when a diff was not captured or is disabled by policy; it cannot recover past code
from counts. To capture future task-file diffs deliberately, first obtain the
appropriate consent and approve `capture.privacy.rawCode: true`, then run:

```bash
uv run --no-sync agent-capture snapshot --workspace /path/to/task \
  --git-dir /path/to/synthetic-data/shadow.git --participant P01 \
  --condition ai-assisted --session S1 --protocol /path/to/approved-protocol.yaml \
  --code-file task.py
```

Use the same session keys as TERN and the participant's declared capture setup.
Repeat `--code-file` only for explicit task source files. Hidden paths,
non-source extensions and parent/absolute paths are rejected. Review the selected
files for embedded secrets; filename checks cannot detect them. Symlinks escaping
the task directory are rejected. Git pathspecs are literal and textconv/external
diff execution is disabled. Patches over 64,000 characters are omitted explicitly.

This opt-in changes what is collected; do not enable it merely to improve a demo.
Metadata-only capture, consent and the researcher's approved protocol remain the
default. Generic event reads hide raw diffs; replay and scoped exports check the
current study policy. Local shadow repositories are sensitive even if ignored by
Git and must follow the operator's consent and retention procedures.
