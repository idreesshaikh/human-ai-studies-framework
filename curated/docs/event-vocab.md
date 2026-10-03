# Curated event vocabulary (schema v5)

This document describes the event shape used by the experimental mining
package. It mirrors the live event envelope, but the package does not submit
rows to the server or provide a mining job in the feature-frozen release.
Curated event types are registered as **schema version 5** in the middleware's
`KNOWN_EVENT_SCHEMA_VERSIONS`; consumers branch on version, never guess.

Join keys, reinterpreted for mined units (see `curated/src/curated/contract.py`):

| Key | Live meaning | Mined meaning |
| --- | --- | --- |
| `participantId` | the enrolled participant | the anonymized **actor unit** (developer / repo / agent), salted-hash pseudonym, never a raw login |
| `condition` | the assigned arm | the adapter's declared comparison arm (e.g. `agent-pr` / `human-pr`) |
| `sessionId` | one session | the mined **activity unit** (a PR, an issue thread, a commit-batch window) |
| `ts` | event time | the **source's** event time, never import time |
| `seq` | producer ordinal | the adapter's deterministic ordinal per `(sessionId, source)`; re-mining is idempotent under the existing unique constraint |
| `source` | the instrument | the local `archive` adapter |

All payloads are **content-free by default**: sizes, counts, timings, flags,
and salted hashes only. Raw identities, commit-message text, and code content
are never emitted. The archive adapter remains content-free. Public-data ethics
are still ethics.

## Event types

| Type | `sessionId` | Payload (content-free) |
| --- | --- | --- |
| `mined_pull_request` | `pr-<repo>-<number>` | `changedFiles`, `additions`, `deletions`, `commits`, `reviewComments`, `authorIsAgent`, `firedHeuristics[]` |
| `mined_commit` | the PR it belongs to | `additions`, `deletions`, `changedFiles`, `authorIsAgent` |
| `mined_review` | the PR it belongs to | `state`, `authorIsAgent` |
| `mined_issue_event` | `issue-<repo>-<number>` | `action`, `authorIsAgent` |
| `mined_actor_snapshot` | the actor's first activity unit | reserved event shape; not emitted by the local archive adapter |

`authorIsAgent` is an **inference**, decided by the versioned heuristic registry
(`curated/src/curated/heuristics.py`); every firing heuristic (`id@version`) is
included in the normalized event. Static metrics and checked-out snapshots are
outside this package.
