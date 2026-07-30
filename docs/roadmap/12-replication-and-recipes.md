# Phase 12: Replication kit & published-paper recipes

> Read first: `requirements/srs.md` §FR-PROT-7, §FR-ANA-5, `protocol/export.py`.
> **Satisfies:** FR-PROT-7, FR-ANA-5, RQ-F3. **Status:** ✅ built.

## The idea

Replicability, demonstrated on our own study: analyses package as reusable
recipes and studies as replication kits, such that a third party reproduces the
report from the kit alone. And "papers become recipes": a published paper's
analysis method runs as a built-in, cited recipe on your data, so "replicate the
literature's designs" is real, not aspirational.

## What it builds

- `protocol/export.py`: `protocol export replication-kit`: the frozen protocol,
  schema + recipe versions, the anonymized dataset, and the report, packaged
  into one byte-stable archive.
- Published-paper recipes in `analysis/recipes/`: `ziegler-acceptance-rate`
  (AI-acceptance rate) and `meyer_fragmentation.py` (work fragmentation), two
  cited replications proving FR-ANA-5.

## Acceptance

- A fresh checkout + the kit regenerates `report.md` byte-for-byte (RQ-F3); the
  archive itself is byte-identical across runs (NFR-6).

## Verification

- `uv run pytest protocol analysis`: the reproduction test
  (`protocol/tests/test_export.py`) and the recipe replications on constructed
  datasets with hand-countable answers.
