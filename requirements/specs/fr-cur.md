# FR-CUR: Curated datasets & mining (detailed specification)

**SRS family:** FR-CUR. **Phase:** 16 (FR-CUR-1..3); FR-CUR-4 deferred.

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

## 3. The GitHub adapter (FR-CUR-2, S)

1. Sources: repositories, PRs (+ reviews, timelines), commits, issues
   via the REST/GraphQL APIs; agent-authored activity identified by the
   heuristics catalogued in `mining-coding-agent-activity` and
   `aidev-ai-coding-agents-github` (bot flags, co-author trailers,
   agent-signature patterns). Each heuristic *named and versioned* in
   the dataset's validity-threats record.
2. Operational posture (NFR-4): token-scoped, rate-limit-aware
   (secondary limits honored with backoff), resumable from a cursor
   (mining jobs are long; interruption must not restart), responses
   cached; degrades to cache when offline. Job progress is visible in
   the UI (FR-LIT-6's no-frozen-UI rule generalizes).
3. Sampling is specified, not improvised: the protocol's curated-path
   section declares the sampling frame (query, date window, inclusion
   rules, target n) *before* mining runs: the mined equivalent of
   FR-ETH-1's "approved protocol is the executed protocol".

Fit criteria: F2.1 a 100-repo mining job interrupted at 50 resumes
without duplicates; F2.2 the adapter refuses to run without a
protocol-declared sampling frame; F2.3 rate-limit exhaustion pauses
with a visible, plain-language status: never a crash or silent stall.

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

## 5. Archive import (FR-CUR-4, C, deferred)

Published replication packages (`devgpt-developer-chatgpt`-style
archives, our own FR-PROT-7 kits) import behind the same normalizer
contract. Design constraint recorded now: our replication kit is the
reference input: the platform must be able to eat its own exports.
