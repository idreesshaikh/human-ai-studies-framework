# Mega-Prompt 08 - Pilot Study (the evaluation)

> Self-contained: execute this file in a fresh working session at the repo
> root. This phase is mostly *conducted*, not coded - the prompt produces the
> study kit and analysis, the humans produce the data.

**Depends on:** 02–07 all done
**Status:** 🔶 In-week slice done (2026-07-12): protocol frozen v1.0, study
kit + `scripts/smoke.sh` + seeded demo shipped, dry run PASS with 7
findings logged (`study/pilot/dry-run-report.md`). Conducted sessions and
the final post-mortem pass await ethics approval + participants (per this
prompt's own "real participants may land after the sprint week") - see the
MP-08 row in `requirements/traceability.md`.

## Context

The framework is the thesis contribution; this study is its evaluation. Two
things are evaluated at once: (a) the pilot's own RQs (AI assistance vs.
cognitive load / code quality / behavior), and (b) the framework RQs - did
the protocol-as-requirements-spec actually drive the study end-to-end, and
where did it leak? Both write into the thesis.

## RE traceability

This phase validates the *entire* traceability matrix: after the study, every
RQ must have a data-backed answer or a documented gap.

## Deliverables

1. **Finalized protocol** - `protocol/examples/pilot-study.yaml` completed
   and frozen (version-tagged): 4–8 participants, within-subjects with
   counterbalanced task order, two ~45-min sessions each (ai-assisted /
   unassisted), two comparable Python tasks.
2. **Study kit** (`study/pilot/`): facilitator runbook (setup checklist
   generated from the protocol: extension install, settings via
   `protocol derive overlay-settings`, middleware up, dry-run), participant
   info sheet + consent form, task descriptions, ethics-application text
   (university template).
3. **Dry run + production packaging (sprint day 7, NFR-9)** - one full fake
   session (you as participant) through the whole stack: `docker compose
   up` from a clean checkout → extension → middleware → dashboard live view
   + task board → `analysis run` → report → `analysis paper`. Ship the
   smoke-test script (`scripts/smoke.sh`: bring-up, health checks, replay
   ingest, dataset export, report generation - exit nonzero on any failure)
   and the seeded demo mode. Every defect found goes in the findings log
   (FR-META-1); fix blockers before real participants. Real participants
   may land after the sprint week - the dry run is the in-week proof.
4. **Conducted sessions** - real participants (Idrees recruits; the platform
   tracks progress on the dashboard).
5. **Analysis + framework post-mortem** (`study/pilot/findings.md`):
   pilot-RQ results from the recipe report, plus the framework evaluation -
   setup time actually spent per participant, protocol fields that were
   missing/wrong (requirements defects!), traceability gaps. Frame defects
   in RE vocabulary: elicitation misses, specification ambiguities,
   validation-gate escapes.

## Acceptance criteria

- Ethics gate satisfied before any real participant (the lifecycle engine
  must literally show this).
- Every collected session ingested with zero seq gaps (or gaps documented).
- `report.md` answers every pilot RQ; `findings.md` answers every framework
  RQ with evidence.

## Verification

- The dashboard's lifecycle board shows the study in `analysis`/`write-up`
  with all gates green. Update `docs/archive/roadmap/00-VISION.md` tracker and
  `requirements/traceability.md` (final status pass over every requirement).
