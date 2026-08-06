# FR-CUR: Curated datasets & mining (detailed specification)

**SRS family:** FR-CUR. **Phase:** 16 (FR-CUR-1/3); FR-CUR-4 shipped Phase 24
Slice B.

## 1. Context

Half the empirical human-AI literature never runs a live session: it
mines repositories, PRs, and conversation archives
(`speed-at-cost-of-quality-cursor`, `aidev-ai-coding-agents-github`,
`agentic-much-adoption`, `devgpt-developer-chatgpt`). The platform's
"dataset exists?" branch makes that path first-class. The architectural
bet, inherited: **the join-key event schema is the convergence
contract**: curated rows land in the same one-timeline shape as live
rows, so every recipe, report, figure, and paper-draft mechanism works
unchanged on mined data.

## 2. The normalizer contract (FR-CUR-1, M)

1. A curated dataset is produced by a **mining adapter** (per source)
   emitting events through one normalizer contract:
   - Join keys, reinterpreted for mined units and *documented as such*:
     `participantId` = the anonymized actor unit (developer, repo, or
     agent, declared per dataset, salted-hash pseudonyms);
     `condition` = the study's comparison arm (e.g. `pre-adoption` /
     `post-adoption`, `agent-pr` / `human-pr`); `sessionId` = the
     mined activity unit (PR, issue thread, commit-batch window);
     timestamps = the source's own event times (never import time).
   - `source` column (the phase 12 per-producer stream mechanism) names the
     adapter; `seq` = the adapter's deterministic ordinal, so re-mining
     is idempotent under FR-ING-2 exactly like replayed live batches.
   - Schema version: curated event types are registered in the same
     versioned event vocabulary (schema v5 candidate); consumers branch,
     never guess (NFR-4).
2. Event vocabulary (initial): `mined_commit`, `mined_pull_request`,
   `mined_review`, `mined_issue_event`, `mined_actor_snapshot`: all
   content-free by default (sizes, counts, timings, salted hashes;
   FR-ETH-2 discipline extends to *other people's* data: mined authors
   are pseudonymized by construction, and public-data ethics are still
   ethics: the protocol's ethics section covers mined subjects too).
3. Static metrics over mined code reuse the existing metrics leg
   against checked-out snapshots (the shadow-git machinery, D14,
   pointed at mined refs). No second metrics pipeline.

Fit criteria:
- F1.1 A curated demo dataset runs the full analysis chain unchanged:
  ingest → gap report (per-source) → dataset export → recipes → per-RQ
  report → paper draft. Zero recipe-layer changes.
- F1.2 Re-running the same mining job produces zero duplicate rows.
- F1.3 Grep-the-output: no mined event payload contains a raw author
  identity, commit message text, or code content unless the protocol's
  content policy explicitly scopes it (FR-AGENT-5 mechanism reused).

## 3. The GitHub adapter (FR-CUR-2) — removed 2026-08-06

FR-CUR-2 (a GitHub PR/commit/issue mining adapter) was built, then retired
at the owner's direction along with its UI entry point (the Data tab's
"Curate from GitHub" card), its job runner (`middleware/mining.py`), its
HTTP routes (`/mining-jobs*`, `/curated-datasets*`), and its fetcher
(`middleware/github_fetch.py`). No other requirement depended on it: the
normalizer contract (FR-CUR-1) and the validity-threats record (FR-CUR-3)
are adapter-agnostic and are exercised today by the archive adapter
(FR-CUR-4, `curated/src/curated/archive_adapter.py`). `curated/heuristics.py`
(the agent-authorship catalogue this section used) is kept as shared
FR-CUR-3 infrastructure, since `curated/threats.py` still imports it.
See `requirements/traceability.md`'s FR-CUR-2 row and
`requirements/build-vs-adopt.md`'s D39 for the removal record.

## 4. Validity-threats record (FR-CUR-3, S)

Mandatory companion of every curated dataset:

```yaml
samplingFrame: {query, window, inclusionRules, exclusions}
heuristics: [{id, version, knownFailureModes, cite}]
biases: [{description, direction, mitigation|accepted}]
coverage: {requested, retrieved, dropped: {reason: count}}
```

Rendered in the platform beside the dataset, injected verbatim into
the report's and paper draft's threats-to-validity section (FR-ANA-4/6):
honesty about provenance travels with every claim (NFR-8 extended to
data, per `mining-coding-agent-activity`'s pitfalls and
`ai-agents-that-matter`'s reproducibility critique).

Fit: F3.1 a curated study's generated paper draft contains the
threats section populated from this record with its heuristic
citations; F3.2 a dataset without the record fails validation at the
gate before `analysis` (lifecycle-enforced, like every artifact).

## 5. Archive import (FR-CUR-4, C)

Published replication packages (`devgpt-developer-chatgpt`-style
archives, our own FR-PROT-7 kits) import behind the same normalizer
contract. Design constraint recorded now: our replication kit is the
reference input: the platform must be able to eat its own exports.
