# agent-capture - the agent interaction leg (MP-12)

The fourth instrument leg: the AI's side of an `ai-assisted` session, on the
same timeline and join keys as every other leg. Primary source is **Claude
Code in the VS Code integrated terminal** (decision D13) - the only
mainstream agent tool with lossless, machine-readable capture.

Satisfies FR-AGENT-1/2/3/5 and FR-INST-15/16/17. Read
`docs/archive/roadmap/12-agent-interaction-leg.md` and the MP-12 row of
`requirements/traceability.md` (including the deviation log) before changing
anything here.

## How capture works

```
Claude Code session
  ├─ .claude/settings.json hooks ──(live)──▶ agent-capture-hook ─┐
  │   (SessionStart/PostToolUse/Stop/SessionEnd)                 │  POST /ingest/events
  └─ ~/.claude/projects/.../<id>.jsonl ──(backstop)──▶ import ───┘  (source: agent-capture)
```

Both paths call the **same** `transcript.normalize_transcript()`. Because the
normalized `seq` is the transcript's append-only position, a live hook and
the post-session import of the same session produce identical
`(session, source, seq)` keys, so ingestion **reconciles** them (FR-ING-2)
instead of duplicating - and a middleware that was down mid-session is fully
recovered by the importer afterwards (NFR-2). Hooks are fire-and-forget with
a short timeout and always exit 0: a down middleware never stalls the agent
(NFR-1).

## Content policy (FR-AGENT-5)

Every conversation string passes one choke point, `redact.py`:

| policy | effect |
| --- | --- |
| `metadata-only` (pilot default) | text stripped entirely - only sizes/counts/timings survive |
| `redacted` | string literals + identifiers ≥ N chars masked |
| `full` | passthrough (explicit consent clause only) |

The policy is **protocol-declared** (`instruments.agentCapture.contentPolicy`)
and baked into the hook command by `protocol derive agent-hooks` - no side
channel (FR-PROT-4). `redact.POLICY_DESCRIPTIONS` are the plain-language
sentences the consent form interpolates verbatim.

## Producer streams

One study session is written by several independent fire-and-forget
producers; each owns a private `seq` stream tagged by `source`, so they
share the session join key without colliding and each stream's completeness
is separately checkable (see `middleware/db.py`):

| source | events | producer |
| --- | --- | --- |
| `agent-capture` | `agent_session_meta`, `agent_turn`, `tool_call` | hooks + importer |
| `workspace-snapshot` | `workspace_snapshot` | `snapshot.py` (shadow git, D14) |
| `participant-git` | `git_commit` (content-free) | `snapshot.py` (observed) |
| `task-harness` | `task_outcome` | `harness.py` (pytest) |
| `agent-derived` | `reliance_loop`, `edit_burst_annotation`, `code_evolution` | `correlate.py`, `evolution.py` |

## Commands

```bash
# Generate the hook pack for a task workspace (content policy from protocol):
uv run protocol derive agent-hooks protocol/examples/pilot-study.yaml \
    > <task-workspace>/.claude/settings.json

# Facilitator runbook exports the join keys:
export STUDY_PARTICIPANT=P01 STUDY_CONDITION=ai-assisted STUDY_SESSION=S1

# Session-runner instruments (run on save / timer / session end):
uv run agent-capture snapshot --workspace <ws> --git-dir .study-data/shadow.git
uv run agent-capture harness  --tests-dir <ws>/task-tests
uv run agent-capture import   <transcript.jsonl> --content-policy metadata-only

# Post-ingest cross-leg correlation + code evolution:
uv run agent-capture correlate --study pilot-2026 --server http://127.0.0.1:8000
```

Feeds MP-06's agent swimlane / conversation viewer and MP-07's
`agent-interaction-dynamics` + `task-outcome-by-condition` recipes.
