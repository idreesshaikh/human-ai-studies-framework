# Phase 11: Paper draft & self-improvement retrospective

> Read first: `requirements/srs.md` §FR-ANA-6, §FR-META.
> **Satisfies:** FR-ANA-6, FR-META-1/2/3. **Status:** 🔶 partial.

## The idea

The write-up phase is a build artifact, and the framework studies itself. From a
completed study the platform generates a paper draft; from its own operation it
logs defects as findings and drafts an inert, human-approved retrospective. The
framework's flaws are data (RQ-F2), and improvement is change-managed: nothing
self-applies.

## What it builds

- `analysis/paper.py`: `analysis paper`: Markdown + LaTeX skeleton with methods
  synthesized from the frozen protocol, results/figures/tables per RQ from the
  recipe report, related work from the paper↔protocol links, and every generated
  claim carrying its traceability tag (`%% trace:`). Deterministic (FR-ANA-6).
- `middleware` findings log (FR-META-1): auto-scan for seq gaps, gate blocks,
  and recipe requires-failures, each linked to the requirement it evidences;
  `POST /findings` for facilitator notes. (Phase 18 briefly extended this with
  a `feedback` kind for in-conversation platform feedback, FR-CONV-5.1; that
  extension was removed 2026-08-06 — see `requirements/srs.md` §FR-CONV-5.)
- `analysis/retrospective.py`: `analysis retrospective`: an LLM-drafted,
  human-approved changelist proposal (FR-ETH-4 boundary grep-tested, offline
  template fallback, inert until applied).

## Remaining

- **FR-META-3: in-platform agents:** scheduled autonomous middleware workflows
  over the FTS5 index that surface cards and inert proposals; specced, extended
  by phase 18's machinery, not yet built.

## Verification

- `uv run pytest analysis`: golden-file paper draft + tectonic compile; the
  retrospective boundary is grep-tested.
