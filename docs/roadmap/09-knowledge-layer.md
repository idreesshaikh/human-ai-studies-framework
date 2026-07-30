# Phase 09: Knowledge layer (papers, graph, assistant)

> Read first: `requirements/srs.md` §FR-LIT, `requirements/specs/fr-lit.md`.
> **Satisfies:** FR-LIT-1/2/3/4/6, FR-ETH-4. **Status:** ✅ built.

## The idea

The literature is the product's knowledge, not background reading. Papers enter
by arXiv ID / DOI / PDF; a citation graph grows around them (ResearchRabbit-style
on open data); papers link to the protocol elements they justify; and a grounded
assistant answers questions over the papers, protocol, and *aggregate* data:
every answer cited, never seeing a row-level participant event (FR-ETH-4).

## What it builds

In `middleware/`:
- `paper_index.py` + FTS5: full-text index the assistant retrieves over.
- `semantic_scholar.py` + `pdf.py`: metadata enrichment (self-paced to the API
  budget, cached) and PDF text extraction.
- citation graph: references/citations/recommendations edges + stub nodes,
  rendered as the constellation (FR-LIT-2).
- paper↔protocol links seeded from the protocol `literature:` list (FR-LIT-3).
- `assistant.py`: the LLM tool-use loop (D32 Mistral); the FR-ETH-4 boundary is
  enforced in code (no tool returns a row-level event; grep-the-output test).

In `platform/`: the **Library** tab: live ingest, the citation constellation
(deterministic force layout), the library list, and the grounded assistant.

## Acceptance

- The assistant cites its sources and degrades gracefully with no LLM key
  (FR-LIT-4); the library never appears frozen on a slow API call (FR-LIT-6).
- The assistant sees only aggregates (FR-ETH-4), enforced server-side.

## Verification

- `uv run pytest middleware`: ingest, FTS, graph, and the assistant boundary
  (grep-the-output).
