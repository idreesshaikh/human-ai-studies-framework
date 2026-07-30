# Phase 10: Corpus at scale + idea↔paper matching

> Read first: `requirements/specs/fr-lit.md`, `docs/papers/README.md`.
> **Satisfies:** FR-LIT-7/8/9/10. **Status:** 🔶 partial.

## The idea

The corpus is quality-first and uncapped (1,000 papers is the floor, not the
ceiling) in two provenance tiers: hand-curated seeds (Tier A, per-paper "why")
plus a harvested, quality-gated, API-verifiable extension grown by citation
snowballing (Tier B). Nothing is ever synthesized: unverifiable candidates are
dropped. Papers are *matched to the researcher's idea* as the conversation
unfolds, and the whole knowledge set is explorable as a living constellation.

## What it builds

- `scripts/corpus_harvest.py`: the re-runnable, resumable pipeline: Semantic
  Scholar snowballing, a quality gate, metric-rich scoring (citations,
  influential citations, recognized venue, open-access, freshness, seed
  connectivity), and `--propose-tier-a` shortlists → `docs/papers/CORPUS.md` +
  `corpus-index.json` (generated, never hand-edited).
- `middleware/corpus_importer.py`: lands both tiers as `Paper(tier=…)` rows +
  FTS + `harvested-via` seed edges under the platform-corpus scope.
- `middleware/matching.py`: the FR-LIT-9 match ladder: FTS BM25 + a
  seed-connectivity rung + optional LLM rerank; `/papers/match` and one-click
  `/papers/from-match` (the match reason is kept as elicitation evidence).

## Acceptance

- The corpus floor is met with API-verified rows; `corpus-verify` is green
  (FR-LIT-8).
- Matching degrades to FTS relevance with no LLM key (FR-LIT-9).

## Remaining

- A committed re-harvest run; the living-constellation animation + scoped RAG
  (FR-LIT-10); the provider-swap decision (FR-LIT-7).

## Verification

- `uv run pytest middleware` (matching, importer); `middleware corpus-verify`.
