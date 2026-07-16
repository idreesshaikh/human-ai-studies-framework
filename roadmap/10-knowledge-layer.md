# Mega-Prompt 10 - Knowledge Layer: Papers, Literature Graph, Claude Assistant

> Self-contained: execute this file in a fresh working session at the repo
> root. Read first: `roadmap/00-VISION.md`, `requirements/srs.md` (FR-LIT-*,
> FR-ETH-4), `requirements/build-vs-adopt.md` (D7, D8, D10), and the
> middleware API. **Verify Claude-API model IDs, pricing, and
> tool-use patterns against the current official API docs before writing
> any Claude-API code - not from memory.**

**Depends on:** 04 (middleware hosts everything); dashboard mount points
from 06. **Satisfies:** FR-LIT-1, FR-LIT-2, FR-LIT-3, FR-LIT-4, FR-ETH-4;
completes FR-DASH-8. **Sprint day 6 (with MP-07).**
**Status:** ✅ Done (2026-07-12) - see the MP-10 row in
`requirements/traceability.md` for the deviation log.

## Context

The pre-study/elicitation phase, on-platform: ingest the papers a study
stands on, see the related-work neighborhood as an interactive graph
(the beloved ResearchRabbit view, rebuilt on open data because
ResearchRabbit has no API - D7/D8), tie papers to the protocol elements
they justify, and ask grounded questions. RE thread: literature is
*elicitation evidence* - every instrument/metric in the protocol should
trace to a paper (e.g. Miller's Law → parameter count), and FR-LIT-3 makes
that chain queryable and citable.

## Deliverables

### 1. Paper ingest (FR-LIT-1) - middleware

- `POST /studies/{id}/papers` - multipart PDF upload **or**
  `{arxivId | doi}`. PDF path: extract text + title guess with `pymupdf`;
  then enrich via Semantic Scholar. ID path: fetch metadata directly.
- Semantic Scholar Graph API (D8): `GET /graph/v1/paper/{DOI:...|ARXIV:...}`
  with fields `title,authors,year,venue,abstract,externalIds`. Store
  metadata + extracted full text in the DB; cache every S2 response
  (offline-after-first-fetch, NFR-7). Handle 429s with backoff; no API key
  required at our volume (document the key env var anyway).
- `GET /studies/{id}/papers`, `DELETE .../papers/{pid}`.

### 2. Literature graph (FR-LIT-2) - middleware + dashboard

- Edge harvesting per ingested paper: S2 `references`, `citations`
  (capped, e.g. top-50 by citationCount), and
  `recommendations/v1/papers/forpaper/{id}`. Store as
  `paper_edges(src, dst, kind)` with stub nodes for un-ingested papers.
- `GET /studies/{id}/papers/graph` → nodes (ingested vs. suggested) +
  edges.
- Dashboard panel (fills the MP-06 `knowledge` mount): force-directed
  graph (`d3-force` or `react-force-graph`); ingested papers large/solid,
  suggestions small/hollow; click a suggestion → "add to study" (ingests
  it); click an ingested paper → detail drawer (abstract, links,
  protocol-links editor). Filter by edge kind. This view must feel like
  ResearchRabbit: seed → neighborhood → grow.

### 3. Paper ↔ protocol links (FR-LIT-3)

- Protocol schema (MP-02) gains `literature:` - a list of
  `{paperRef, justifies: [RQ-P2, instrument:static-metrics, metric:parameter_count, ...]}`.
- Middleware endpoint to read/write links; detail drawer edits them;
  traceability chips (FR-DASH-6) and the MP-11 paper draft's related-work
  section consume them.

### 4. Knowledge assistant (FR-LIT-4) - middleware + dashboard

- `POST /studies/{id}/assistant` `{question, history}` → streamed answer.
- Claude API with **tool use**; per the current official API docs,
  Sonnet-class model, low temperature. Tools exposed to the model:
  - `search_papers(query)` → chunked full-text search over ingested papers
    (SQLite FTS5 is enough - no vector DB at this scale).
  - `get_protocol()` → the study YAML.
  - `get_dataset_summary()` → **aggregates only**: per-condition counts,
    metric means/medians, event-type totals. FR-ETH-4 is enforced *here*,
    server-side: no tool returns row-level participant events, so the
    model cannot leak what it cannot see.
- System prompt requires citations: every claim tagged `[paper-id §chunk]`,
  `[protocol:field]`, or `[dataset-summary]`; answers without a source must
  say so. Render citations as clickable chips in the chat panel.
- `ANTHROPIC_API_KEY` via env; assistant absent-but-graceful when unset
  (panel explains, everything else works offline).

### 5. Tests

pytest: ingest by DOI (S2 mocked with recorded fixtures), graph assembly
with stub nodes, FTS search, assistant tool-layer returns aggregates only
(the FR-ETH-4 test: assert no event-row fields in any tool output);
one recorded end-to-end assistant exchange with mocked Claude responses.

## Acceptance criteria

- Upload one PDF + add two arXiv IDs → graph renders their shared
  neighborhood; adding a suggested node ingests it and the graph regrows.
- Protocol links round-trip: link a paper to `metric:parameter_count`,
  see it in the traceability chip and in `GET` output.
- Assistant answers "which of our metrics does <ingested paper> justify,
  and what does our data show for it so far?" with correct chips citing
  the paper, the protocol link, and the dataset summary - and refuses
  row-level questions ("show me P03's events") by design.
- All S2/Claude failures degrade gracefully (cached graph still renders;
  panel reports, session capture untouched).

## Verification

- pytest green; live demo of the acceptance flows against the seeded demo
  study; screenshot the graph for the thesis. Update
  `roadmap/00-VISION.md` tracker + `requirements/traceability.md`
  (FR-LIT-1–4, FR-ETH-4 → ✅; FR-DASH-8 → ✅).
