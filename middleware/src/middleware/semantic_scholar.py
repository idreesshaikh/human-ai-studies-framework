"""Semantic Scholar Graph API client (FR-LIT-1/2; decision D8).

The open citation graph the literature view is built on: paper lookup by
DOI / arXiv id, plus the three edge kinds the ResearchRabbit-style view
needs - ``references``, ``citations``, and ``recommendations``. Metadata
only (ids, titles, counts), so NFR-5-compatible - no participant data ever
touches this call, and it is the *sole* external call besides the assistant.

Local-first discipline like the rest of the stack: every response is cached
in the middleware DB by the caller (``S2Cache``), so the graph renders
offline after the first fetch (NFR-7). No API key is required at our volume;
``MIDDLEWARE_S2_API_KEY`` is honoured if set. Failures degrade gracefully -
a :class:`SemanticScholarError` is surfaced as a warning, never blocks a
session, and never discards an already-cached graph.

Papers are keyed by the same canonical ``paperRef`` scheme the protocol's
``literature:`` list and the Zotero importer use (``doi:``/``arxiv:``, else
``s2:<paperId>``), so neighbours join protocol links by construction.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

GRAPH_API = "https://api.semanticscholar.org/graph/v1"
REC_API = "https://api.semanticscholar.org/recommendations/v1"

PAPER_FIELDS = "title,authors,year,venue,abstract,externalIds,citationCount"
EDGE_FIELDS = "title,year,externalIds,citationCount"

#: Cap harvested edges per kind (top-N by citationCount) so the graph stays
#: legible and one popular paper doesn't pull thousands of stubs.
EDGE_CAP = 50


class SemanticScholarError(Exception):
    """S2 could not serve a request (surfaced as a warning; cached graph kept)."""


def _headers() -> dict[str, str]:
    key = os.environ.get("MIDDLEWARE_S2_API_KEY")
    return {"x-api-key": key} if key else {}


def get_json(url: str, *, retries: int = 3) -> object:
    """GET with 429 backoff (S2 rate-limits anonymous callers). Monkeypatched
    in tests with recorded fixtures - the one network seam."""
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=_headers())
        try:
            with urllib.request.urlopen(req, timeout=20) as res:
                return json.loads(res.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < retries - 1:
                time.sleep(2**attempt)
                continue
            raise SemanticScholarError(f"GET {url} -> HTTP {exc.code}") from exc
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            raise SemanticScholarError(f"GET {url} failed: {exc}") from exc
    raise SemanticScholarError(f"GET {url} rate-limited after {retries} tries")


def s2_id_for_ref(paper_ref: str) -> str:
    """Our ``paperRef`` -> the S2 path id (``DOI:...``/``ARXIV:...``/hash)."""
    if paper_ref.startswith("doi:"):
        return "DOI:" + paper_ref[len("doi:") :]
    if paper_ref.startswith("arxiv:"):
        return "ARXIV:" + paper_ref[len("arxiv:") :]
    if paper_ref.startswith("s2:"):
        return paper_ref[len("s2:") :]
    return paper_ref


def ref_for_paper(paper: dict) -> str:
    """Canonical ``paperRef`` for an S2 paper object (matches the protocol
    scheme so links join): DOI first, else arXiv, else the S2 hash."""
    ext = paper.get("externalIds") or {}
    if ext.get("DOI"):
        return f"doi:{str(ext['DOI']).lower()}"
    if ext.get("ArXiv"):
        return f"arxiv:{ext['ArXiv']}"
    return f"s2:{paper.get('paperId', '')}"


def normalize_paper(paper: dict) -> dict:
    """One S2 paper object -> our paper record shape (matches zotero.py)."""
    authors = [a.get("name", "") for a in (paper.get("authors") or []) if a.get("name")]
    ext = paper.get("externalIds") or {}
    return {
        "paperRef": ref_for_paper(paper),
        "s2Id": paper.get("paperId", ""),
        "title": paper.get("title") or "",
        "authors": authors,
        "year": paper.get("year"),
        "venue": paper.get("venue") or "",
        "abstract": paper.get("abstract") or "",
        "doi": str(ext.get("DOI") or "").lower(),
        "arxivId": ext.get("ArXiv") or "",
        "url": (
            f"https://www.semanticscholar.org/paper/{paper.get('paperId')}"
            if paper.get("paperId")
            else ""
        ),
        "citationCount": paper.get("citationCount"),
    }


def fetch_paper(paper_ref: str, *, fetch=get_json) -> dict:
    """Metadata for one paper by ref (FR-LIT-1 id path). ``fetch`` is the GET
    seam - the app passes a DB-caching wrapper (NFR-7); tests monkeypatch
    :func:`get_json`."""
    sid = urllib.parse.quote(s2_id_for_ref(paper_ref), safe=":")
    paper = fetch(f"{GRAPH_API}/paper/{sid}?fields={PAPER_FIELDS}")
    if not isinstance(paper, dict):
        raise SemanticScholarError(f"unexpected paper shape for {paper_ref!r}")
    return normalize_paper(paper)


def _neighbours(items: list, inner_key: str) -> list[dict]:
    """Top-N neighbour papers (by citationCount) from an edges response."""
    papers = []
    for item in items or []:
        paper = item.get(inner_key) if isinstance(item, dict) else None
        if isinstance(paper, dict) and paper.get("paperId"):
            papers.append(paper)
    papers.sort(key=lambda p: p.get("citationCount") or 0, reverse=True)
    return papers[:EDGE_CAP]


def fetch_edges(paper_ref: str, *, fetch=get_json) -> dict[str, list[dict]]:
    """The three edge kinds for one ingested paper (FR-LIT-2), each a list of
    normalized neighbour records. Any single kind failing degrades to [] for
    that kind rather than losing the others."""
    sid = urllib.parse.quote(s2_id_for_ref(paper_ref), safe=":")
    out: dict[str, list[dict]] = {
        "references": [], "citations": [], "recommendations": []
    }
    graph = f"{GRAPH_API}/paper/{sid}"
    for kind, url in (
        ("references", f"{graph}/references?fields={EDGE_FIELDS}&limit=100"),
        ("citations", f"{graph}/citations?fields={EDGE_FIELDS}&limit=100"),
        (
            "recommendations",
            f"{REC_API}/papers/forpaper/{sid}?fields={EDGE_FIELDS}&limit=50",
        ),
    ):
        try:
            body = fetch(url)
        except SemanticScholarError:
            continue
        if kind == "recommendations":
            papers = _neighbours(
                [{"p": p} for p in (body.get("recommendedPapers") or [])], "p"
            )
        else:
            inner = "citingPaper" if kind == "citations" else "citedPaper"
            papers = _neighbours(body.get("data") or [], inner)
        out[kind] = [normalize_paper(p) for p in papers]
    return out
