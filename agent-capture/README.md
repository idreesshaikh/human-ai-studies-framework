# agent-capture - an optional producer

`agent-capture` records provider-side interaction for studies that need it. It
uses the same session, source, and sequence contract as TERN, but it is never
required for a basic live study. A Claude Code hook, a generic JSON transcript,
or another adapter can supply the raw stream; the package does not depend on a
specific model or provider for its event contract.

Provider transcript content is the only capture surface that can contain
conversation text. Its policy (`instruments.agentCapture.contentPolicy`:
metadata-only, redacted, or full) is stated in consent and derived from the
protocol rather than configured on the side.

## How capture works

```
Provider session (Claude Code example)
  ├─ provider hooks ──(live)──▶ agent-capture-hook ─┐
  │   (SessionStart/PostToolUse/Stop/SessionEnd)                 │  POST /ingest/events
  └─ provider transcript ──(backstop)──▶ import ─────┘  (source: agent-capture)
```

Both paths call the same `transcript.normalize_transcript()`. Because the
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

The policy is protocol-declared (`instruments.agentCapture.contentPolicy`)
and baked into the hook command by `protocol derive agent-hooks` - no side
channel (FR-PROT-4). The policy descriptions live in `protocol.capture` so the
consent layer and the producer use one shared contract.

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
# Derive the same manifest used by TERN and save it locally for external tools:
uv run protocol derive session-manifest protocol/examples/pilot-study.yaml \
    --participant P01 --condition ai-assisted --session s-example \
    > .phoenix/session-manifest.json

# Optional producer commands consume the same manifest:
uv run agent-capture snapshot --manifest .phoenix/session-manifest.json \
    --workspace <task-workspace> --git-dir .study-data/shadow.git

# Session-runner instruments (run on save / timer / session end):
uv run agent-capture snapshot --workspace <ws> --git-dir .study-data/shadow.git
uv run agent-capture harness  --tests-dir <ws>/task-tests
uv run agent-capture import   <transcript.jsonl> --manifest .phoenix/session-manifest.json

# Post-ingest cross-leg correlation + code evolution:
uv run agent-capture correlate --manifest .phoenix/session-manifest.json
```

For a protected server, set `MIDDLEWARE_TOKEN` or pass `--token` to
`correlate`; the token is used only for the dataset read.

The raw stream feeds the platform's agent view and the
`agent-interaction-dynamics` and `task-outcome-by-condition` recipes. The
`correlate` and `evolution` commands are post-ingest derivations; they do not
replace the raw event stream.
