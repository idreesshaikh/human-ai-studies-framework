# Dry-run report - pilot-2026 (MP-08 deliverable 3, sprint day 7)

**Date:** 2026-07-12 · **Facilitator-as-participant:** P00 (deliberately
off-roster) · **Verdict: PASS** - the stack drove a full fake study
end-to-end from the frozen protocol; 7 findings logged (FR-META-1), none
blocking recruitment except the actions listed at the end.

This file is the `pilot` phase's gate artifact (upload via
`POST /ingest/files`).

## What ran (all from a clean `docker compose up -d --build`)

1. **Packaging (NFR-9):** `scripts/smoke.sh` → `SMOKE OK`: bring-up,
   health (`studyId pilot-2026`, protocol loaded, schema v2+v3 known),
   dashboard SPA served at `/`, idempotent replay ingest, one-timeline
   dataset export with join keys (JSON + CSV), per-RQ report generation.
2. **The fake sessions:** `study/pilot/dry_run_sessions.py` posted P00's
   counterbalanced pair in the extension's schema-v3 wire format -
   `S-P00-dry-ai` (ai-assisted, Task A texture: 34 events, 5 suggestion
   lifecycles 3 accepted/2 dismissed, origins human/ai/paste, 2 fatigue
   probes, TLX debrief) and `S-P00-dry-un` (unassisted, Task B texture:
   23 events, 2 stuck episodes, higher fatigue/TLX). Result: **zero seq
   gaps** (34/34, 23/23); every row flagged `unknown-participant` -
   correct, P00 is off-roster, so dry-run rows can never masquerade as a
   roster participant's.
3. **Static-metrics leg:** real orchestrator runs over two stand-in "final
   workspaces", one per condition, join keys + `--timestamp` stamped;
   14 + 9 rows ingested (also flagged, consistent).
4. **Analysis:** `analysis run` over the live dataset → 7/9 plan entries
   executed, report organized by RQ with exact tests + effect sizes +
   per-cell n (e.g. fatigue: exact Mann-Whitney p=0.500, Cliff's delta
   -1.00, ai n=3/un n=1, "hypothesis-generating" framing). The two RQ-P5
   entries failed validation **loudly, naming `agent_turn` and
   `task_outcome`** - the MP-12 instruments, exactly as designed
   (FR-ANA-2). Recipe runs were recorded back to the middleware, so the
   dashboard's un-run-recipe cards clear.
5. **Lifecycle (the FR-ETH-1 acceptance criterion):** the board computes
   `design: complete → ethics: current`; data-collection is mechanically
   unreachable without `ethics-approval.pdf` + `consent-form.pdf`, while
   dry-run ingest still flowed (ingest never gates - NFR-1). Both
   behaviors observed live.

## Findings logged (full text in the middleware `/findings` store and in `findings.md` §3)

| ID | Requirement | One line | Class |
| -- | ----------- | -------- | ----- |
| DR-01 | FR-INST-8 | suggestion size only on `accepted` → size-quartile accept rate not computable (schema v4 fix) | specification defect |
| DR-02 | FR-INST-4 | metrics `--out` is a directory writing two files; runbook had it as one file - corrected | specification ambiguity |
| DR-03 | FR-ANA-2 | protocol can't say "instrument planned, not shipped" → smoke must whitelist MP-12 event types | specification incompleteness |
| DR-04 | FR-ING-4 | demo seed is ai-assisted-only → demo comparisons all degrade to descriptives | elicitation miss |
| DR-05 | FR-ETH-3 | demo seed uses roster IDs P01/P02 → would blend with real data; runbook now resets the volume | validation-gate escape risk |
| DR-06 | FR-INST-13 | overlay never yet driven by a human hand (scripted verifications only) | validation gap |
| DR-07 | FR-AGENT-1 | RQ-P5 uninstrumented until MP-12; fails loudly at plan validation | traceability gap (planned) |

## Required before the first real participant

1. Ethics approval + consent form uploaded (the gate enforces this).
2. One interactive dev-host session of the overlay (DR-06).
3. `docker compose down -v` and fresh bring-up + artifact re-upload (DR-05).
4. MP-12 built if RQ-P5 is to be answered for real participants (DR-07) -
   otherwise sessions run without the agent leg and RQ-P5 stays a
   documented gap.
