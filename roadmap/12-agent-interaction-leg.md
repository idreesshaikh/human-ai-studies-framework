# Mega-Prompt 12 - Agent Interaction Leg (+ task harness & snapshots)

> Self-contained: execute this file in a fresh working session at the repo
> root. Read first: `roadmap/00-VISION.md`, `requirements/srs.md`
> (FR-AGENT-*, FR-INST-14/15/16, FR-ETH-2 rev 2, FR-AGENT-5),
> `requirements/build-vs-adopt.md` (D13, D14), and the middleware API.
> **Before writing hook configs or the transcript importer, verify current
> Claude Code hook names, hook JSON shapes, and transcript JSONL format
> against the current official docs - not from memory.**

**Depends on:** 04 (middleware). Feeds MP-06 (agent swimlane, conversation
view) and MP-07 (two recipes). **Satisfies:** FR-AGENT-1, FR-AGENT-2,
FR-AGENT-3, FR-AGENT-5; FR-INST-14 lands in the overlay alongside;
FR-INST-15, FR-INST-16, FR-INST-17 land here as session-runner concerns
(FR-INST-17 added 2026-07-12, `requirements/metric-coverage.md`).
**Sprint day 4 (with MP-05 - both are capture legs).**
**Status:** ✅ Done (2026-07-12) - see the MP-12 row in
`requirements/traceability.md` for the deviation log.

## Context

The fourth instrument leg: without it the framework records a conversation's
*echoes* (pastes, injections) but not the conversation. The pilot's
`ai-assisted` condition standardizes on **Claude Code in the VS Code
integrated terminal** (D13) because it is the only mainstream agent tool
with lossless machine-readable capture: real-time hooks + on-disk transcript
JSONL. Everything lands in the same middleware, same join keys, same
timeline. This phase also carries the two session-runner instruments that
came out of the same gap analysis: workspace snapshots (FR-INST-15) and the
task-outcome harness (FR-INST-16) - both are "what actually happened to the
code/task" ground truth that the agent leg's story is interpreted against.

## Deliverables

### 1. Agent event types (middleware-side schema, versioned like all legs)

| type | payload |
| ---- | ------- |
| `agent_session_meta` | `{ agentTool: "claude-code", modelId, agentSessionId, cwdHash }` - emitted at agent-session start; links agent events to the study session. |
| `agent_turn` | `{ role: user\|assistant, turnIndex, chars, codeBlocks: [{language, chars, lines}], latencyMs?, content? }` - `content` present only per content policy (see 4). |
| `agent_tool_call` | `{ toolName, durationMs, success, targetHash? }` - which tools the agent used (edits, bash, reads); never raw arguments at `metadata-only`. |
| `task_outcome` | `{ trigger: save\|session-end, passed, failed, total, timeToFirstGreenMs? }` (FR-INST-16). |
| `workspace_snapshot` | `{ commitHash, trigger: save\|timer, filesChanged, insertions, deletions }` (FR-INST-15). |
| `git_commit` | `{ hash, filesChanged, insertions, deletions }` - the participant's *own* commits in the task repo, content-free (no message text, FR-ETH-2); detected by the snapshotter diffing `git log` of the task repo per tick (FR-INST-17). |

Schema-v4 items to land with this leg (both found at MP-07/08, see DR-01
and `requirements/metric-coverage.md`): `ai_suggestion` records `charCount`
at `shown` (not only at `accepted`) so accept-rate-by-size-quartile becomes
computable, and `edit_burst` carries `startLine`/`endLine` so AI-code
**persistence** can be computed line-level rather than approximated.

### 2. Claude Code capture (`agent-capture/`) - FR-AGENT-2

- **Hook pack**: a generated `.claude/settings.json` hooks section for the
  task workspace (produced by `protocol derive agent-hooks <protocol>`,
  extending FR-PROT-4's no-side-channel rule). Hooks POST their JSON to
  `http://localhost:8000/ingest/events` wrapped in the StudyEvent envelope
  (join keys injected via environment variables the facilitator runbook
  sets: `STUDY_PARTICIPANT`, `STUDY_CONDITION`, `STUDY_SESSION`). Hook
  scripts must be fire-and-forget with a short timeout - a down middleware
  must never stall the participant's agent (NFR-1 applies to the agent
  too).
- **Transcript importer** (`agent-capture/import_transcript.py`): parses
  the session's transcript JSONL from `~/.claude/projects/<workspace>/`,
  normalizes to the event types above, and ingests post-session. Because
  ingestion is idempotent (FR-ING-2), hook-captured and imported events
  reconcile rather than duplicate - key on `(agentSessionId, turnIndex)`.
  The importer is the **completeness backstop**; hooks are the **liveness
  source** (dashboard live view during sessions). Where the transcript
  carries token-usage metadata, the importer SHALL lift it into
  `agent_turn` (`inputTokens`/`outputTokens` - metadata, allowed at every
  content policy; see `requirements/metric-coverage.md` §4).

### 3. Correlation job (middleware) - FR-AGENT-3

Post-ingest (or on dataset export), correlate across legs per session:
- `agent_turn` (assistant, with code blocks) → `clipboard_paste` /
  `edit_burst(origin: ai|paste)` within a configurable window and size
  tolerance ⇒ annotate the burst with `agentTurnRef` (strengthens
  FR-INST-10's classification with ground truth).
- `clipboard_paste` (external/terminal-bound) → next `agent_turn(user)` →
  later code-paste-back ⇒ emit a derived `reliance_loop` span event
  (start/end, turn refs). Derived events are marked `derived: true` and
  never overwrite raw data.

### 4. Content policy enforcement (`agent-capture/redact.py`) - FR-AGENT-5

One choke point through which every `content?` field passes before storage:
`metadata-only` strips text entirely (default); `redacted` masks string
literals and identifiers ≥ N chars; `full` passes through. The active
policy comes from the protocol; the consent-form generator (MP-08 study
kit) interpolates the policy's plain-language description verbatim. Tests
prove no content survives `metadata-only` (grep-the-output pattern, same
as the FR-ETH-4 test).

### 5. Session-runner instruments

- **Workspace snapshotter** (`agent-capture/snapshot.py`, D14): shadow git
  repo (`--git-dir=<study-data>/shadow.git --work-tree=<task workspace>`),
  commit on save-event webhook + every N minutes; emits
  `workspace_snapshot` events. The participant's own git usage is
  untouched but *observed*: new commits in the task repo's `git log` are
  emitted as content-free `git_commit` events (FR-INST-17). MP-03's
  orchestrator can then run per-snapshot → metric time series.
- **Code-evolution derivation** (FR-INST-17, computed at session end from
  the shadow-git series + origin-classified bursts, emitted as
  `derived: true` events or dataset columns): gross/net LOC added/deleted
  over the session, within-session **churn** (lines added then reworked or
  removed before session end), and **AI-code persistence** (fraction of
  AI-origin insertions surviving to session end - Ziegler et al.'s second
  measure; line-level once bursts carry line ranges, else approximated by
  chars and stated as such in recipe methods).
- **Task harness** (`agent-capture/harness.py`): runs the task's
  acceptance tests (pytest) on session end + optionally on save, emits
  `task_outcome`. Task repos for the pilot ship a `task-tests/` directory;
  time-to-first-green computed from the first all-pass event.

### 6. Dashboard + recipes handoff (notes for MP-06/07, already specced there)

Agent lane in the session timeline (turns as markers, tool calls as ticks,
reliance loops as spans); a conversation viewer (respecting content
policy - `metadata-only` shows turn structure only); recipes
`agent-interaction-dynamics` and `task-outcome-by-condition`.

### 7. Tests

pytest: transcript-fixture import (recorded real transcript, anonymized),
hook-payload normalization, idempotent reconcile (hooks + import of same
session), correlation window logic (synthetic fixture with known loops),
redaction levels, snapshotter commit triggers, harness outcome events.

## Acceptance criteria

- A scripted session - participant asks Claude Code to fix a bug, pastes
  an error, applies the fix, tests go green - produces: live hook events
  during the session, a reconciled (no-duplicate) event set after
  transcript import, ≥ 1 `reliance_loop` derived span, `edit_burst` rows
  annotated with `agentTurnRef`, `workspace_snapshot` commits, and a
  `task_outcome` with `timeToFirstGreenMs`.
- Switching the protocol to `metadata-only` and re-running stores zero
  conversation text (test-enforced).
- Middleware down mid-session: the agent keeps working, hooks fail
  silently, transcript import recovers everything afterward (NFR-2's
  best-effort-mirror + backstop story, demonstrated).

## Verification

- pytest green; run the scripted session end-to-end against the live
  stack; show the timeline's agent lane. Update `roadmap/00-VISION.md`
  tracker + `requirements/traceability.md` (FR-AGENT-1/2/3/5,
  FR-INST-15/16/17 → ✅; FR-INST-14 with MP-05).
