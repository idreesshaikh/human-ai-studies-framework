# Pilot study findings & framework post-mortem - pilot-2026

MP-08 deliverable 5. A living document: the dry run (2026-07-12) wrote the
framework-RQ evidence below; the conducted sessions append to §2, §4, and
§5. Every defect here is framed in RE vocabulary and mirrored as a
structured finding in the middleware `/findings` store (FR-META-1), linked
to the requirement ID it evidences.

## 1. Framework RQ answers (evidence as of the dry run)

### RQ-F1 - Specification: did the protocol drive the study end-to-end?

**Yes, with three enumerated leaks.** From the single frozen YAML the
framework mechanically derived: the instrument settings
(`protocol derive overlay-settings` → the exact `cognitiveOverlay.*` keys
the extension declares), the middleware's study identity, roster validation
and condition vocabulary, the lifecycle board and its gates, the task
board's cards, the analysis plan (which recipes run, which RQ each answers,
what the report contains), and the smoke test's expectations. Nothing in
the dry run was hand-configured except the leaks, which are the answer's
other half - each was insufficient *specification*, not missing code:

- DR-01: the event schema under-specifies suggestion-size capture
  (recorded only at `accepted`), so a specified analysis (FR-ANA-3
  size-quartile accept rates) is underivable.
- DR-02: the metrics CLI's output contract (`--out` = directory, two
  files) existed only in code, not in specification - the runbook drafted
  it wrong on first writing.
- DR-03: the protocol schema cannot express "instrument declared but not
  yet shipped", so plan validation cannot distinguish a planned gap
  (MP-12) from a broken instrument, and downstream tooling whitelists
  event types by hand.

### RQ-F2 - Traceability: did the chain surface defects before data collection?

**Yes - measurably.** The requires-check failed the two RQ-P5 recipes at
*plan-validation time*, naming the missing event types (`agent_turn`,
`task_outcome`) - a design defect surfaced before any participant was
scheduled (DR-07). The report's validation section carries the same
message, and the recipe-run feed clears the dashboard's un-run-recipe
cards, so coverage is visible per RQ. The findings log itself demonstrates
the chain: all seven dry-run defects attach to requirement IDs. Setup
effort: machine-side bring-up from a clean checkout is one command +
`scripts/smoke.sh` (minutes, dominated by the Docker build); per-participant
human setup time is measured in §4 during the real sessions.

### RQ-F3 - Replicability

**Pipeline-level yes; kit-level lands with MP-09.** One published analysis
(Ziegler et al. 2022) runs as a protocol-named recipe on the shared
dataset; the dry run is bit-replayable (`dry_run_sessions.py` is
deterministic - its second run deduplicated 57/57 events); the report is
regenerable from the exported dataset alone (`analysis run --dataset`).
The third-party re-import test is MP-09 item 2.

## 2. Pilot RQ answers

**Pending real participants** (post-sprint, per the mega-prompt). The dry
run proved each pipeline with facilitator data - see
`results/pilot-2026/report.md` after any `analysis run`:

| RQ | Pipeline status at dry run |
| -- | -------------------------- |
| RQ-P1 | fatigue/stuck/TLX recipes produce exact tests + effect sizes + per-cell n across both conditions |
| RQ-P2 | 9-metric comparison with Cliff's-delta-first reporting |
| RQ-P3 | paste size/frequency distributions by condition |
| RQ-P4 | review latency, scroll coverage of AI bursts, accept rates; + the Ziegler replication |
| RQ-P5 | **documented gap:** blocked on MP-12 instruments; fails loudly at validation (DR-07) |

## 3. Defect log (RE-classified)

The authoritative copies live in the middleware findings store
(`GET /findings`, source `mp-08-dry-run`); summary:

| ID | Requirement | Defect | RE class |
| -- | ----------- | ------ | -------- |
| DR-01 | FR-INST-8 | suggestion size absent at `shown` → specified analysis underivable | specification defect |
| DR-02 | FR-INST-4 | metrics CLI output contract undocumented; runbook wrong on first draft | specification ambiguity |
| DR-03 | FR-ANA-2 | no planned-vs-shipped instrument state in the protocol schema | specification incompleteness |
| DR-04 | FR-ING-4 | demo seed single-condition → demo comparisons degenerate | elicitation miss |
| DR-05 | FR-ETH-3 | demo rows use roster IDs; would blend with real data (mitigated: volume reset in runbook) | validation-gate escape risk |
| DR-06 | FR-INST-13 | overlay verified scripted, never by a human hand; gates first participant | validation gap |
| DR-07 | FR-AGENT-1 | RQ-P5 uninstrumented until MP-12; loud at plan validation | traceability gap (planned) |

## 4. Setup-time ledger (fill per participant)

| Participant | Session | Setup min | Friction notes → finding ID |
| ----------- | ------- | --------- | --------------------------- |
| P00 (dry run) | both | - (scripted; machine bring-up: one command + smoke) | DR-02 |
| P01 | 1 | | |
| ... | | | |

## 5. Final traceability pass (complete after the last session)

To be filled with: per-RQ answer-or-documented-gap verdicts, protocol
fields that were missing/wrong during real sessions, seq-gap incidents
(target: zero or documented), withdrawal count, and the retrospective
input (FR-META-2, MP-11).
