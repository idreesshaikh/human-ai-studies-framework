# Evidence

The **Evidence** tab holds the papers behind a study, the protocol decisions
each one supports, and related literature. Paper counts and citations describe
the collection; they do not establish the quality or validity of a study.

<figure markdown="span">
  ![The Evidence tab with the paper link field, Add paper and Upload PDF, and an empty paper list](../assets/screens/evidence-light.webp#only-light)
  ![The Evidence tab with the paper link field, Add paper and Upload PDF, and an empty paper list](../assets/screens/evidence-dark.webp#only-dark)
  <figcaption>Evidence for a study with no papers yet. Papers accepted from recommendations in Setup appear here too.</figcaption>
</figure>

## Add and find papers

Paste an arXiv or DOI link, or enter its identifier, in **Paper link or identifier**.
Choose **Add paper**, or use **Upload PDF** for a researcher-supplied file. Failed
lookups preserve the input and explain how to try again.

Once a study has six or more papers, you can filter them by title, author, year
or identifier, and sort them by recently added, title or
**Newest publication**. Templates and design recommendations stay in Templates
and Setup.

The desktop collection and reader have equal, stable heights. Long collections
scroll inside the list; long abstracts scroll inside the reader. Author summaries
keep rows compact, with the full list under **View all *N* authors**.

## Read and connect

Select a paper to read its bibliographic details and abstract. **Open source**
opens the article's public identifier or source page. Add protocol identifiers,
such as `RQ-1`, to **Protocol links**, then choose **Save links**. Unsaved drafts
remain available when switching between papers; saving reports the server result.

**Remove paper** asks for confirmation before removing the paper and its links
from the study. Read access includes saved links; edit access can change the
collection.

## Explore related work

The literature map shows references, later citations and similar work. Select a
related paper to inspect its details, then choose **Add to study** if it belongs
in the collection. Citation updates keep the reading pane available.

Use the zoom buttons or Ctrl/Command plus scroll to zoom; ordinary scrolling
continues through the page. Drag the map background to pan and choose **Fit** to
frame the visible papers. Arrow keys move between papers; Enter or Space opens
their details. Map labels remain readable across screen sizes and zoom levels.

Local development can import the literature corpus with:

```bash
uv run --no-sync python -m middleware corpus-import
```

## Keeping the library current

A refresh searches arXiv and Semantic Scholar for recent metadata and stores
unseen papers as candidates. It does not fetch PDFs. Candidates are not searchable
until a researcher accepts them. The Evidence tab shows when the last refresh ran
and how many candidates await review; an incomplete or failed refresh is identified.

```bash
uv run --no-sync python -m middleware corpus-refresh --dry-run
uv run --no-sync python -m middleware corpus-refresh
uv run --no-sync python -m middleware corpus-candidates --limit 20
uv run --no-sync python -m middleware corpus-decide --ref arxiv:2610.00000 --decision accept --note "Reviewed title and abstract; relevant to this study area"
uv run --no-sync python -m middleware corpus-decide --ref arxiv:2610.00001 --decision reject --note "Model benchmark without developer participants"
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
Set `MIDDLEWARE_S2_API_KEY` if available and `MIDDLEWARE_CONTACT_EMAIL` for an arXiv
contact address. No source failure silently counts as a successful refresh.

Paper metadata includes data from Semantic Scholar and arXiv. Recommendation
abstracts are omitted from conversation exports and replication kits; this also
keeps Semantic Scholar abstracts out of those exports. Uploaded researcher files
remain the researcher's responsibility. Review Semantic Scholar's caching and
reuse terms before storing or sharing abstracts.
