# Mega-Prompt 02 - Study Protocol Schema + Lifecycle State Machine

> Self-contained: execute this file in a fresh working session at the repo
> root. Read `docs/archive/roadmap/00-VISION.md` and `requirements/srs.md` first.

**Depends on:** 01 (requirement IDs, glossary terms)
**Status:** ✅ Done (2026-07-11)

## Context

The platform's central claim: a study protocol is a machine-readable
requirements specification ("study-as-code"). This phase builds the artifact
that makes the claim concrete: a validated YAML protocol format plus the
study lifecycle state machine that consumes it. The Cognitive Overlay already
takes `participantId` + `condition` as settings - the protocol becomes the
single source those flow from.

## RE traceability

Satisfies FR-PROT-1, FR-PROT-2, FR-PROT-3, FR-PROT-4, FR-PROT-5; advances
FR-ETH-1 (gate side) and NFR-4 (`protocolVersion`). Rows flipped in
`requirements/traceability.md` on completion (2026-07-11).

## Objective

A Python package `protocol/` that can load, validate, and interrogate a study
protocol, plus the lifecycle engine.

## Deliverables

1. **Protocol schema** (`protocol/schema/study-protocol.schema.json`, JSON
   Schema draft 2020-12, authored once, validating the YAML): metadata
   (title, researchers, ethics ref), research questions with IDs, conditions
   (e.g. `ai-assisted` / `unassisted`), participant plan (count, assignment
   strategy: within/between-subjects, counterbalancing), instruments (which
   legs run, with their config - fatigue interval, stuck thresholds, the
   `cognitiveOverlay.behavior.*` thresholds and language/path filters of
   FR-INST-10/12, metric set), session plan (duration, task description),
   phases + gates (see 3), analysis plan (which recipes answer which RQ),
   consent/ethics artifacts, and a `literature:` section
   (`{paperRef, justifies: [...]}` links per FR-LIT-3 - consumed by
   Mega-Prompt 10; schema field lands now so the version doesn't churn).
2. **Example protocol** (`protocol/examples/pilot-study.yaml`) - our real
   with/without-AI pilot, fully filled in. This file later drives
   Mega-Prompt 08.
3. **Lifecycle state machine** (`protocol/lifecycle.py`) - phases:
   `design → ethics → pilot → recruitment → data-collection → analysis →
   write-up`, each with entry gates (required artifacts / approvals) and the
   query API: current phase, missing artifacts, allowed transitions. Gates
   are requirements-validation checkpoints - say so in the docstrings.
4. **Validator + CLI** (`protocol/cli.py`): `protocol validate <file>`,
   `protocol status <file>` (phase + missing items), `protocol derive
   overlay-settings <file>` - emits the `cognitiveOverlay.*` settings JSON
   for a given participant/condition, proving the protocol drives the
   instruments.
5. Unit tests (pytest) for schema validation, gate logic, and settings
   derivation; malformed-protocol fixtures.

## Implementation guidance

- Python 3.12+, `pyyaml` + `jsonschema`; keep it dependency-light.
- Version the schema (`protocolVersion` field) from day one - mirror the
  discipline of the extension's `SCHEMA_VERSION`.
- Conditions and instrument names must use glossary terms.

## Acceptance criteria

- The pilot example validates; deliberately broken fixtures fail with
  human-readable messages naming the offending field.
- `derive overlay-settings` output can be pasted into VS Code settings and
  accepted by the Cognitive Overlay unchanged.
- Lifecycle refuses to enter `data-collection` while the ethics gate is
  unsatisfied.

## Verification

- `pytest` green; run the CLI against the example and one broken fixture and
  show output. Update `docs/archive/roadmap/00-VISION.md` tracker and
  `requirements/traceability.md`.
