# Curated event vocabulary (schema v5)

The curated-dataset leg (FR-CUR) emits events in the same one-timeline shape
a live instrument produces, so every downstream recipe/report/paper
mechanism works unchanged. Curated event types are registered as **schema
version 5** in the middleware's `KNOWN_EVENT_SCHEMA_VERSIONS`; consumers
branch on version, never guess.

Join keys, reinterpreted for mined units (see `curated/src/curated/contract.py`):

| Key | Live meaning | Mined meaning |
| --- | --- | --- |
| `participantId` | the enrolled participant | the anonymized **actor unit** (developer / repo / agent), salted-hash pseudonym — never a raw login |
| `condition` | the assigned arm | the study's comparison arm (e.g. `agent-pr` / `human-pr`) |
| `sessionId` | one session | the mined **activity unit** (a PR, an issue thread, a commit-batch window) |
| `ts` | event time | the **source's** event time, never import time |
| `seq` | producer ordinal | the adapter's deterministic ordinal per `(sessionId, source)` — re-mining is idempotent under the existing unique constraint |
| `source` | the instrument | the adapter (`github`, …) |

All payloads are **content-free by default**: sizes, counts, timings, flags,
and salted hashes only. Raw identities, commit-message text, and code content
appear only when the protocol's content policy explicitly scopes them (the
FR-AGENT-5 mechanism, reused). Public-data ethics are still ethics.

## Event types

| Type | `sessionId` | Payload (content-free) |
| --- | --- | --- |
| `mined_pull_request` | `pr-<repo>-<number>` | `changedFiles`, `additions`, `deletions`, `commits`, `reviewComments`, `authorIsAgent`, `firedHeuristics[]` |
| `mined_commit` | the PR it belongs to | `additions`, `deletions`, `changedFiles`, `authorIsAgent` |
| `mined_review` | the PR it belongs to | `state`, `authorIsAgent` |
| `mined_issue_event` | `issue-<repo>-<number>` | `action`, `authorIsAgent` |
| `mined_actor_snapshot` | the actor's first activity unit | `isAgent`, `firedHeuristics[]` |

`authorIsAgent` is an **inference**, decided by the versioned heuristic
registry (`curated/src/curated/heuristics.py`); every firing heuristic
(`id@version`) is recorded and lands in the dataset's validity-threats
record. Static metrics over mined code reuse the existing metrics leg against
checked-out snapshots (the shadow-git machinery) — there is no second metrics
pipeline.
