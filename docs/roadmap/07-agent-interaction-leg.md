# Phase 07: Agent-interaction leg

> Read first: `agent-capture/README.md`, `requirements/srs.md` §FR-AGENT.
> **Satisfies:** FR-AGENT-1/2/3/5, FR-INST-15/16/17. **Status:** ✅ built.

## The idea

The fourth leg: the AI's side of an `ai-assisted` session, on the same timeline
and join keys as every other leg. The agent is a study subject too: its
conversation turns, tool calls, and session metadata are structured events, and
they *correlate* with editor events so the human-agent interaction dynamic
(reliance loops) is measurable, not two silos.

## What it builds

`agent-capture/` (Python package; CLIs `agent-capture`, `agent-capture-hook`):
- `hook.py` + `import_transcript.py`: Claude Code hooks POST in real time; the
  on-disk transcript JSONL is imported as a completeness backstop. One
  normalizer reconciles both idempotently (D13).
- `snapshot.py`: a shadow-git workspace snapshotter so static metrics become a
  time series and code evolution is reconstructable (FR-INST-15).
- `harness.py`: runs a task's acceptance tests at session end, recording
  pass/fail and time-to-first-green as events (FR-INST-16).
- `correlate.py`: reliance loops (error → agent → code-paste) and burst
  annotation (FR-AGENT-3); `evolution.py` derives churn / AI-code persistence
  (FR-INST-17).
- `redact.py`: the content-policy choke point (`metadata-only` default);
  conversation content is the one scoped exception, consent-matched (FR-AGENT-5).

## Acceptance

- Agent events land on the shared timeline with join keys (FR-AGENT-1).
- Default `metadata-only` stores zero conversation text (grep-the-output test);
  `git_commit` events are content-free (hashes/counts, never message text).

## Verification

- `uv run pytest agent-capture`: normalizer idempotency, harness, correlate,
  redaction boundary.
