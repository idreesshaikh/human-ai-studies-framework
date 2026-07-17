# Mega-Prompt 09 - Replication Kit, Zotero, Second Paper Recipe

> Self-contained: execute this file in a fresh working session at the repo
> root. Execute after 08; pick items à la carte by remaining time.
> *(Renamed from `09-stretch-integrations.md`; literature ingest, the paper
> graph, and the assistant were promoted into core scope as Mega-Prompt 10.)*

**Depends on:** 08 (the core slice must be proven first)
**Satisfies:** FR-PROT-7, FR-LIT-5, FR-ANA-5, NFR-6.
**Status:** ✅ Done (2026-07-12) - all three items shipped and demo-verified;
see the MP-09 row in `requirements/traceability.md` (FR-PROT-7, FR-LIT-5,
FR-ANA-5, NFR-6, RQ-F3 all ✅). Deviations recorded there.

## Items (in order of thesis value per effort)

1. **Replication kit export** (FR-PROT-7) - `protocol export
   replication-kit`: one archive containing the frozen protocol, schema +
   recipe versions, pinned dependency lockfiles, the anonymized dataset,
   ingested-paper metadata + protocol links, and the report. **The test is
   reproduction:** a fresh checkout + the kit regenerates `report.md` and
   `paper/draft.tex` bit-for-bit modulo timestamps (NFR-6). This makes
   "replicate entire studies in a standard way" a demonstrated claim for
   our own study - the strongest RQ-F3 evidence available.
2. **Zotero import** (FR-LIT-5) - read a collection via the Zotero local
   HTTP API (fall back to web API + key) into the study's paper set;
   items flow through the existing FR-LIT-1 ingest path, so the graph and
   assistant pick them up for free. Proves the ingest extension point.
3. **Second replicated-paper recipe** (FR-ANA-5 deepened) - implement one
   more published developer-study analysis as a recipe, cited in the
   docstring; strengthens the papers-become-recipes argument beyond a
   single example. Preferred candidates (2026-07-12,
   `requirements/metric-coverage.md`): Ziegler et al.'s **persistence** of
   accepted completions, or a GitClear-style within-session **churn**
   analysis - both computable from FR-INST-17's code-evolution series once
   MP-12 lands, and both squarely in the papers-become-recipes thesis.

## Acceptance criteria

Per item: end-to-end demo; the relevant requirement rows flipped in
`requirements/traceability.md`; item 1 additionally passes the
fresh-checkout reproduction test.

## Verification

Per item, demo + tests; update `docs/archive/roadmap/00-VISION.md` tracker.
