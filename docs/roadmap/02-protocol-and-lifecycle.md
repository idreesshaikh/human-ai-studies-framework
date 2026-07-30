# Phase 02: Study protocol & lifecycle

> Read first: `requirements/srs.md` §FR-PROT, `docs/design/state-machines.md` §1.
> **Satisfies:** FR-PROT-1..5/7/9, FR-ETH-1. **Status:** ✅ built.

## The idea

A study is one validated YAML protocol: the single document of record. It
declares metadata, RQs, conditions, the participant plan, instruments + config,
the session plan, phases + gates, the analysis plan, and literature links.
Everything downstream (instrument config, lifecycle gating, data validation,
analysis, the paper) derives from the protocol alone; any needed side-channel
configuration is a specification defect (RQ-F1).

## What it builds

`protocol/` (Python package, CLI `protocol`):
- `loader.py` + `schema/`: parse and validate against a published JSON Schema;
  `validate_protocol` is exposed for in-memory callers (the compiler, the
  template registry). `protocolVersion` is a schema-shape enum (1 human /
  2 curated / 3 agent participants); consumers branch on it, never guess.
- `lifecycle.py`: the state machine `design → ethics → pilot → recruitment →
  data-collection → analysis → write-up`, each transition guarded by gate
  artifacts; reports current phase and missing artifacts.
- `derive.py`: `derive overlay` / `derive agent-hooks`: instrument config from
  the protocol, no hand-maintained side config (FR-PROT-4).
- `export.py`: the replication-kit export (FR-PROT-7, detailed in phase 12).

CLI: `protocol validate | status | derive | export replication-kit`.

## Acceptance

- The analysis plan maps every RQ to the recipes that answer it, and coverage
  is checkable (FR-PROT-5).
- Ethics approval and consent are gate artifacts: `data-collection` is
  unreachable without them (FR-ETH-1).
- The agent-participant fixture `protocol/tests/fixtures/agent-participant-v3.yaml`
  validates; overlay-derive fails cleanly on it and `derive agent-hooks` works.

## Verification

- `uv run pytest protocol`: schema, lifecycle, derive, and version-branching.
- Derived settings match the protocol key-for-key.
