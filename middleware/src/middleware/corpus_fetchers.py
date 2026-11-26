"""
Live arXiv and Semantic Scholar fetchers for the refresh job (URL builders are
pure). Semantic Scholar goes through :mod:`middleware.semantic_scholar`, the one
client that paces, retries and times out every S2 request.
"""

from __future__ import annotations

import os
import threading
import time
import urllib.parse
import urllib.request

from middleware import semantic_scholar

ARXIV_API = "https://export.arxiv.org/api/query"
S2_FIELDS = semantic_scholar.SEARCH_FIELDS
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


def s2_bulk_url(query: str, since: str, until: str, token: str | None) -> str:
    """A bulk-search page published within ``since..until``, newest first."""
    return semantic_scholar.bulk_search_url(
        query, since=since, until=until, token=token
    )


def _user_agent() -> str:
    contact = os.environ.get("MIDDLEWARE_CONTACT_EMAIL", "").strip()
    return "StudyLoop-corpus-refresh" + (f" (mailto:{contact})" if contact else "")


def arxiv_ids_url(ids: list[str]) -> str:
    """Metadata for specific arXiv ids (``id_list``), one entry per id."""
    params = {"id_list": ",".join(ids), "max_results": len(ids)}
    return f"{ARXIV_API}?{urllib.parse.urlencode(params)}"


def fetch_arxiv(
    query: str, since: str, until: str, start: int, max_results: int
) -> bytes:
    """One arXiv API page, paced to the published limit of one request per 3 s."""
    return _arxiv_get(arxiv_url(query, since, until, start, max_results))


def fetch_arxiv_by_ids(ids: list[str]) -> bytes:
    """Atom entries for the given arXiv ids (the abstract backfill's fallback)."""
    return _arxiv_get(arxiv_ids_url(ids))


def _arxiv_get(url: str) -> bytes:
    global _arxiv_last
    with _arxiv_lock:
        wait = ARXIV_MIN_INTERVAL_S - (_clock() - _arxiv_last)
        if wait > 0:
            _sleep(wait)
        req = urllib.request.Request(  # noqa: S310 - fixed HTTPS endpoint
            url, headers={"User-Agent": _user_agent()}
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as res:  # noqa: S310
                return res.read()
        finally:
            _arxiv_last = _clock()


def fetch_s2(query: str, since: str, until: str, token: str | None) -> dict:
    """One Semantic Scholar bulk-search page (up to 1,000 papers and a token)."""
    return semantic_scholar.search_bulk(query, since=since, until=until, token=token)
