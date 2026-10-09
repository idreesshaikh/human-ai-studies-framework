# Evidence

The Evidence tab holds the papers used to design a study, their protocol links,
and related literature. Paper counts and citations describe the collection;
they do not establish the quality or validity of a study.

## Add and find papers

Paste an arXiv or DOI link, or enter its identifier, in **Paper link or identifier**.
Choose **Add paper**, or use **Upload PDF** for a researcher-supplied file. Failed
lookups preserve the input and explain how to try again.

Filter study papers by title, author, year or identifier. Sort by recently added,
title or publication year. Templates and design recommendations remain available
in Templates and Setup.

## Read and connect

Select a paper to read its bibliographic details and abstract. **Open source**
opens the article's public identifier or source page. Add protocol identifiers,
such as `RQ-1`, to **Protocol links**, then choose **Save links**. Unsaved drafts
remain available when switching between papers; saving reports the server result.

**Remove paper** asks for confirmation before removing the paper and its links
from the study. Viewers can read papers and their saved links; owners and members
can change the collection.

## Explore related work

The literature map shows references, later citations and similar work. Select a
related paper to inspect its details, then choose **Add to study** if it belongs
in the collection. Citation updates keep the reading pane available.

Use the zoom buttons or Ctrl/Command plus scroll to zoom; ordinary scrolling
continues through the page. Drag the map background to pan and choose **Fit** to
frame the visible papers. Arrow keys move between papers; Enter or Space opens
their details. Map labels remain readable across screen sizes and zoom levels.

Local development can import the project corpus with:

```bash
uv run python -m middleware corpus-import
```

## Keeping the library current

A refresh searches arXiv and Semantic Scholar for recent metadata and stores
unseen papers as candidates. It does not fetch PDFs. Candidates are not searchable
until a researcher accepts them. The Evidence tab shows when the last refresh ran
and how many candidates await review; an incomplete or failed refresh is identified.

```bash
uv run python -m middleware corpus-refresh --dry-run
uv run python -m middleware corpus-refresh
uv run python -m middleware corpus-candidates --limit 20
uv run python -m middleware corpus-decide --ref arxiv:2610.00000 --decision accept --note "Reviewed title and abstract; relevant to this study area"
uv run python -m middleware corpus-decide --ref arxiv:2610.00001 --decision reject --note "Model benchmark without developer participants"
```

The example references are placeholders; review actual candidates before deciding.
Accepting is permanent in v1. Accepted papers are tier C, keep their review note,
and live in the database: back up that database. They do not count toward completion
of the checked-in core corpus. Rejecting a candidate excludes it from later imports.

Queries are configured in `docs/papers/refresh-queries.json`, or in a file selected
by `MIDDLEWARE_REFRESH_QUERIES`. Set `MIDDLEWARE_REFRESH_INTERVAL_H=6` to enable
an optional six-hour scheduler; leave it empty for manual refreshes. Every refresh
records its window, counts, and source errors. Only a fully successful run advances
the date watermark; retries overlap by one day. Recent concurrent runs are refused.

arXiv requests are paced to at least three seconds apart. Semantic Scholar requests
use its existing rate limiter and bounded retries; keyless requests can receive 429
responses. A failed source produces a partial run when another source succeeds.
Set `S2_API_KEY` if available and `MIDDLEWARE_REFRESH_CONTACT_EMAIL` for an arXiv
contact address. No source failure silently counts as a successful refresh.

Paper metadata includes data from Semantic Scholar and arXiv. Recommendation
abstracts are omitted from conversation exports and replication kits; this also
keeps Semantic Scholar abstracts out of those exports. Uploaded researcher files
remain the researcher's responsibility. Confirm Semantic Scholar caching terms
with AI2 before deploying abstract storage for other users (open decision D11).
