"""
Live arXiv and Semantic Scholar fetchers for the refresh job (URL builders are
pure).
"""

from __future__ import annotations

import os
import threading
import time
import urllib.parse
import urllib.request

ARXIV_API = "https://export.arxiv.org/api/query"
S2_BULK = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
S2_FIELDS = (
    "title,year,publicationDate,externalIds,abstract,citationCount,venue,authors"
)
ARXIV_MIN_INTERVAL_S = (
    3.0  # arXiv terms: one request every three seconds, one connection
)

_arxiv_lock = threading.Lock()
_arxiv_last = 0.0
_sleep = time.sleep
_clock = time.monotonic


def arxiv_url(query: str, since: str, until: str, start: int, max_results: int) -> str:
    """Submissions between two ISO dates (inclusive), newest first."""
    window = (
        f"submittedDate:[{since.replace('-', '')}0000 TO {until.replace('-', '')}2359]"
    )
    params = {
        "search_query": f"{query} AND {window}",
        "start": start,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    return f"{ARXIV_API}?{urllib.parse.urlencode(params)}"


def s2_bulk_url(
    query: str, since: str, until: str, token: str | None, limit: int
) -> str:
    params = {
        "query": query,
        "publicationDateOrYear": f"{since}:{until}",
        "fields": S2_FIELDS,
        "limit": limit,
        "sort": "publicationDate:desc",
    }
    if token:
        params["token"] = token
    return f"{S2_BULK}?{urllib.parse.urlencode(params)}"


def _user_agent() -> str:
    contact = os.environ.get("MIDDLEWARE_CONTACT_EMAIL", "").strip()
    return "StudyLoop-corpus-refresh" + (f" (mailto:{contact})" if contact else "")


def fetch_arxiv(
    query: str, since: str, until: str, start: int, max_results: int
) -> bytes:
    """One arXiv API page, paced to the published limit of one request per 3 s."""
    global _arxiv_last
    with _arxiv_lock:
        wait = ARXIV_MIN_INTERVAL_S - (_clock() - _arxiv_last)
        if wait > 0:
            _sleep(wait)
        req = urllib.request.Request(  # noqa: S310 - fixed HTTPS endpoint
            arxiv_url(query, since, until, start, max_results),
            headers={"User-Agent": _user_agent()},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as res:  # noqa: S310
                return res.read()
        finally:
            _arxiv_last = _clock()


def fetch_s2(query: str, since: str, until: str, token: str | None, limit: int) -> dict:
    """
    One Semantic Scholar bulk-search page (self-paced, with 429 backoff, by its
    client).
    """
    from middleware import semantic_scholar

    payload = semantic_scholar.get_json(s2_bulk_url(query, since, until, token, limit))
    if not isinstance(payload, dict):
        raise ValueError("Semantic Scholar returned something other than an object")
    return payload
