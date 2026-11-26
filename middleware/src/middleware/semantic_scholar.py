"""Semantic Scholar client: the one way StudyLoop calls S2 (FR-LIT-1/2; D8).

Every request goes through :func:`get_json` or :func:`post_json`. Both

* hold the process to one request per second across *all* endpoints. S2's API
  tutorial gives a key "a 1 request per second rate across all endpoints", so
  the Graph and Recommendations services share one clock;
* retry 429 and 5xx answers and dropped connections with exponential backoff,
  honouring ``Retry-After`` when S2 sends one;
* time out, and never wait past a caller's :func:`budget` (the live chat path
  fails fast instead of queueing behind background traffic).

Tests and the UI regression harness replace ``get_json``/``post_json`` with
fixtures that take only the URL (and payload), so the budget travels in a
context variable rather than an argument.

Endpoints, parameters and fields follow the official OpenAPI documents at
``https://api.semanticscholar.org/{graph,recommendations}/v1/swagger.json``.
"""

from __future__ import annotations

import contextlib
import contextvars
import email.utils
import json
import logging
import math
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

GRAPH_API = "https://api.semanticscholar.org/graph/v1"
REC_API = "https://api.semanticscholar.org/recommendations/v1"

# Paper details and edge neighbours share one shape; the abstract rides along so
# opening a suggested Library node never needs a second request.
PAPER_FIELDS = "title,authors,year,venue,abstract,externalIds,citationCount"
EDGE_FIELDS = PAPER_FIELDS
# Search, bulk search, citations and recommendations also report when a paper
# was published, which the freshness filters and candidate records use.
SEARCH_FIELDS = PAPER_FIELDS + ",publicationDate"

BATCH_MAX_IDS = 500  # POST /paper/batch: "Can only process 500 paper ids at a time"
SEARCH_MAX_LIMIT = 100  # GET /paper/search: limit "Must be <= 100"
CITATIONS_MAX_LIMIT = 1000  # GET /paper/{id}/citations: limit "Must be <= 1000"
RECOMMENDATIONS_MAX_LIMIT = 500  # recommendations: "Maximum 500"
EDGE_CAP = 50

MIN_INTERVAL_S = 1.0
GET_TIMEOUT_S = 20.0
POST_TIMEOUT_S = 60.0
RETRIES = 4
RETRYABLE = frozenset({429, 500, 502, 503, 504})
MAX_RETRY_AFTER_S = 30.0
# A person waiting on a Library action (adding a paper, matching an uploaded PDF)
# waits at most this long, retries included, rather than up to five full
# timeouts and their backoff when S2 hangs or is down.
INTERACTIVE_BUDGET_S = 30.0

# Seams: tests replace these so pacing and backoff never really sleep.
_clock = time.monotonic
_sleep = time.sleep
_urlopen = urllib.request.urlopen

_slot_lock = threading.Lock()
_next_slot = 0.0
_deadline: contextvars.ContextVar[float | None] = contextvars.ContextVar(
    "s2_deadline", default=None
)


class SemanticScholarError(Exception):
    """S2 could not serve a request (surfaced as a warning; cached data kept)."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        retry_after: float | None = None,
    ):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def api_key() -> str:
    return os.environ.get("MIDDLEWARE_S2_API_KEY", "").strip()


def _headers() -> dict[str, str]:
    key = api_key()
    return {"x-api-key": key} if key else {}


@contextlib.contextmanager
def budget(seconds: float) -> Iterator[None]:
    """Requests made inside never wait or retry past ``seconds`` from now."""
    token = _deadline.set(_clock() + seconds)
    try:
        yield
    finally:
        _deadline.reset(token)


def _reserve_slot() -> None:
    """Claim the next free one-second slot, or fail if it lands past the budget."""
    global _next_slot
    limit = _deadline.get()
    with _slot_lock:
        now = _clock()
        start = max(now, _next_slot)
        if limit is not None and start >= limit:
            raise SemanticScholarError("no request slot before the deadline")
        _next_slot = start + MIN_INTERVAL_S
    if start > now:
        _sleep(start - now)


def retry_after_seconds(headers) -> float | None:
    """``Retry-After`` as seconds (delta-seconds or an HTTP date), else None."""
    raw = (headers.get("Retry-After") if headers is not None else None) or ""
    raw = raw.strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        try:
            when = email.utils.parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return None
        value = when.timestamp() - time.time()
    return max(0.0, value) if math.isfinite(value) else None


def _backoff(attempt: int, retry_after: float | None) -> float:
    delay = retry_after if retry_after is not None else 2.0**attempt
    return min(delay, MAX_RETRY_AFTER_S)


def _fits(delay: float) -> bool:
    limit = _deadline.get()
    return limit is None or _clock() + delay < limit


def _request(method: str, url: str, body: bytes | None, timeout: float) -> object:
    headers = _headers()
    if body is not None:
        headers["Content-Type"] = "application/json"
    for attempt in range(RETRIES + 1):
        _reserve_slot()
        limit = _deadline.get()
        wait_s = timeout if limit is None else min(timeout, limit - _clock())
        if wait_s <= 0:
            raise SemanticScholarError(f"{method} {url}: deadline passed")
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with _urlopen(req, timeout=wait_s) as res:
                return json.loads(res.read())
        except urllib.error.HTTPError as exc:
            after = retry_after_seconds(exc.headers)
            delay = _backoff(attempt, after)
            if exc.code in RETRYABLE and attempt < RETRIES and _fits(delay):
                log.info("S2 %s -> HTTP %s; retrying in %.1fs", method, exc.code, delay)
                _sleep(delay)
                continue
            raise SemanticScholarError(
                f"{method} {url} -> HTTP {exc.code}", status=exc.code, retry_after=after
            ) from exc
        except json.JSONDecodeError as exc:
            raise SemanticScholarError(f"{method} {url}: not JSON") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            delay = _backoff(attempt, None)
            if attempt < RETRIES and _fits(delay):
                log.info("S2 %s failed (%s); retrying in %.1fs", method, exc, delay)
                _sleep(delay)
                continue
            raise SemanticScholarError(f"{method} {url} failed: {exc}") from exc
    raise AssertionError("unreachable")  # pragma: no cover


def get_json(url: str) -> object:
    """GET one S2 URL (paced, retried, bounded by any active :func:`budget`)."""
    return _request("GET", url, None, GET_TIMEOUT_S)


def post_json(url: str, payload: dict) -> object:
    """POST JSON to one S2 URL, with :func:`get_json`'s pacing and retries."""
    return _request("POST", url, json.dumps(payload).encode(), POST_TIMEOUT_S)


def build_url(base: str, path: str, **params: object) -> str:
    """``base + path`` with the non-empty params; commas stay readable."""
    query = {k: v for k, v in params.items() if v is not None and v != ""}
    if not query:
        return f"{base}{path}"
    return f"{base}{path}?{urllib.parse.urlencode(query, safe=',:')}"


# --- response cache


def _age_days(fetched_at: str, now: str) -> float | None:
    try:
        then = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
        current = datetime.fromisoformat(now.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    if (then.tzinfo is None) != (current.tzinfo is None):
        return None
    return (current - then).total_seconds() / 86400.0


SEARCH_CACHE_DAYS = 30.0


def prune_search_cache(
    s: Session, *, now: str, older_than_days: float = SEARCH_CACHE_DAYS
) -> int:
    """Delete cached relevance-search answers older than ``older_than_days``.

    Live chat search caches one row per distinct query, so these rows grow with
    use and are never reused once stale. Paper, batch and graph answers are kept:
    they let the Library graph render offline. Returns the rows deleted."""
    from datetime import datetime, timedelta

    from middleware.db import S2Cache

    # Cache rows are stamped "YYYY-MM-DDTHH:MM:SSZ", which sorts as text.
    moment = datetime.fromisoformat(now.replace("Z", "+00:00"))
    cutoff = (moment - timedelta(days=older_than_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale = s.execute(
        delete(S2Cache).where(
            S2Cache.url.like("%/paper/search?%"), S2Cache.fetched_at < cutoff
        )
    )
    return stale.rowcount or 0


def cached_get(
    s: Session, url: str, *, now: str, max_age_days: float | None = None
) -> object:
    """
    A GET served from the ``s2_cache`` table when it holds a fresh copy (D8, NFR-7:
    the graph renders offline after the first fetch). ``max_age_days`` bounds how
    old a reused answer may be; None reuses it forever. Only successes are cached.
    """
    from middleware.db import S2Cache

    # Look up without flushing. An autoflush would write the previous response's
    # cache row, opening SQLite's single write transaction and holding it through
    # the network request below.
    with s.no_autoflush:
        hit = s.scalar(select(S2Cache).where(S2Cache.url == url))
    if hit is None:  # rows added in this session but not yet flushed
        hit = next((o for o in s.new if isinstance(o, S2Cache) and o.url == url), None)
    if hit is not None:
        age = _age_days(hit.fetched_at, now) if max_age_days is not None else 0.0
        if age is not None and (max_age_days is None or age <= max_age_days):
            return hit.body
    body = get_json(url)
    if hit is not None:
        hit.body, hit.fetched_at = body, now
    else:
        s.add(S2Cache(url=url, body=body, fetched_at=now))
    return body


# --- identifiers and records


def s2_id_for_ref(paper_ref: str) -> str:
    """Our ``paperRef`` -> the S2 path id (``DOI:...``/``ARXIV:...``/hash)."""
    if paper_ref.startswith("doi:"):
        return "DOI:" + paper_ref[len("doi:") :]
    if paper_ref.startswith("arxiv:"):
        return "ARXIV:" + paper_ref[len("arxiv:") :]
    if paper_ref.startswith("s2:"):
        return paper_ref[len("s2:") :]
    return paper_ref


def lookup_id(s2_id: str | None, doi: str | None, arxiv_id: str | None) -> str:
    """The id S2 resolves a stored paper by, or "" when it has none."""
    if s2_id:
        return s2_id
    if arxiv_id:
        from middleware.corpus_sources import strip_version

        return f"ARXIV:{strip_version(arxiv_id)}"
    if doi:
        return f"DOI:{doi.strip()}"
    return ""


def ref_for_paper(paper: dict) -> str:
    """
    Canonical ``paperRef`` for a study's own paper (matches the protocol scheme so
    links join): DOI first, else arXiv, else the S2 hash.
    """
    ext = paper.get("externalIds") or {}
    if ext.get("DOI"):
        return f"doi:{str(ext['DOI']).lower()}"
    if ext.get("ArXiv"):
        return f"arxiv:{ext['ArXiv']}"
    return f"s2:{paper.get('paperId', '')}"


def normalize_paper(paper: dict) -> dict:
    """One S2 paper object -> our canonical paper record shape."""
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


def _path_id(paper_id: str) -> str:
    return urllib.parse.quote(paper_id, safe=":")


# --- endpoints


def fetch_paper(
    paper_ref: str, *, fetch: Callable[[str], object] | None = None
) -> dict:
    """Metadata for one paper by ref: ``GET /graph/v1/paper/{paper_id}``."""
    fetch = fetch or get_json
    sid = _path_id(s2_id_for_ref(paper_ref))
    paper = fetch(build_url(GRAPH_API, f"/paper/{sid}", fields=PAPER_FIELDS))
    if not isinstance(paper, dict):
        raise SemanticScholarError(f"unexpected paper shape for {paper_ref!r}")
    return normalize_paper(paper)


def fetch_batch_raw(
    ids: list[str],
    *,
    fields: str,
    post: Callable[[str, dict], object] | None = None,
) -> list[dict | None]:
    """
    ``POST /graph/v1/paper/batch`` for up to 500 ids, ``fields`` as a query
    parameter. One entry per id, in order; None where S2 does not know the id.
    """
    if len(ids) > BATCH_MAX_IDS:
        raise ValueError(f"at most {BATCH_MAX_IDS} ids per batch")
    post = post or post_json
    results = post(build_url(GRAPH_API, "/paper/batch", fields=fields), {"ids": ids})
    if not isinstance(results, list):
        raise SemanticScholarError(f"unexpected batch shape for {len(ids)} ids")
    return [r if isinstance(r, dict) and r.get("paperId") else None for r in results]


def fetch_papers_batch(
    paper_refs: list[str],
    *,
    fields: str = PAPER_FIELDS,
    id_for_ref: Callable[[str], str] = s2_id_for_ref,
    post: Callable[[str, dict], object] | None = None,
) -> dict[str, dict]:
    """Normalized metadata for many refs, in batches of 500; unknown refs absent."""
    out: dict[str, dict] = {}
    askable = [r for r in paper_refs if id_for_ref(r)]
    for start in range(0, len(askable), BATCH_MAX_IDS):
        chunk = askable[start : start + BATCH_MAX_IDS]
        records = fetch_batch_raw(
            [id_for_ref(r) for r in chunk], fields=fields, post=post
        )
        for ref, record in zip(chunk, records, strict=False):
            if record is not None:
                out[ref] = normalize_paper(record)
    return out


def search(
    query: str,
    *,
    limit: int = 20,
    fields: str = SEARCH_FIELDS,
    fetch: Callable[[str], object] | None = None,
) -> list[dict]:
    """
    Relevance-ranked papers for a plain-text query: ``GET /graph/v1/paper/search``.
    Hyphenated terms match nothing there, so hyphens become spaces.
    """
    text = " ".join(query.replace("-", " ").split())
    if not text:
        return []
    fetch = fetch or get_json
    body = fetch(
        build_url(
            GRAPH_API,
            "/paper/search",
            query=text,
            fields=fields,
            limit=max(1, min(limit, SEARCH_MAX_LIMIT)),
        )
    )
    data = body.get("data") if isinstance(body, dict) else None
    if body is not None and not isinstance(body, dict):
        raise SemanticScholarError("search response is not an object")
    return [p for p in data or [] if isinstance(p, dict) and p.get("paperId")]


def bulk_search_url(
    query: str,
    *,
    since: str,
    until: str,
    token: str | None = None,
    fields: str = SEARCH_FIELDS,
    sort: str = "publicationDate:desc",
) -> str:
    """
    ``GET /graph/v1/paper/search/bulk`` published within ``since..until``
    (``publicationDateOrYear``), newest first. The endpoint takes no ``limit``:
    each page holds up to 1,000 papers and a continuation ``token``.
    """
    return build_url(
        GRAPH_API,
        "/paper/search/bulk",
        query=query,
        publicationDateOrYear=f"{since}:{until}",
        fields=fields,
        sort=sort,
        token=token,
    )


def search_bulk(
    query: str,
    *,
    since: str,
    until: str,
    token: str | None = None,
    fields: str = SEARCH_FIELDS,
    fetch: Callable[[str], object] | None = None,
) -> dict:
    """One bulk-search page: ``{"total", "token", "data"}``."""
    fetch = fetch or get_json
    payload = fetch(
        bulk_search_url(query, since=since, until=until, token=token, fields=fields)
    )
    if not isinstance(payload, dict):
        raise SemanticScholarError(
            "bulk search returned something other than an object"
        )
    return payload


def fetch_citations(
    paper_id: str,
    *,
    since: str | None = None,
    until: str | None = None,
    limit: int = 100,
    fields: str = SEARCH_FIELDS,
    fetch: Callable[[str], object] | None = None,
) -> list[dict]:
    """
    Papers citing ``paper_id`` (an S2 id or ``ARXIV:``/``DOI:`` form), optionally
    only those published within ``since..until``: ``GET /paper/{id}/citations``.
    """
    fetch = fetch or get_json
    window = f"{since or ''}:{until or ''}" if since or until else None
    body = fetch(
        build_url(
            GRAPH_API,
            f"/paper/{_path_id(paper_id)}/citations",
            fields=fields,
            limit=max(1, min(limit, CITATIONS_MAX_LIMIT)),
            publicationDateOrYear=window,
        )
    )
    if not isinstance(body, dict):
        raise SemanticScholarError("citations response is not an object")
    return [
        item["citingPaper"]
        for item in body.get("data") or []
        if isinstance(item, dict)
        and isinstance(item.get("citingPaper"), dict)
        and item["citingPaper"].get("paperId")
    ]


def _neighbours(items: list, inner_key: str) -> list[dict]:
    """Top-N neighbour papers (by citationCount) from an edges response."""
    papers = []
    for item in items or []:
        paper = item.get(inner_key) if isinstance(item, dict) else None
        if isinstance(paper, dict) and paper.get("paperId"):
            papers.append(paper)
    papers.sort(key=lambda p: p.get("citationCount") or 0, reverse=True)
    return papers[:EDGE_CAP]


def fetch_edges(
    paper_ref: str, *, fetch: Callable[[str], object] | None = None
) -> dict[str, list[dict]]:
    """
    The three edge kinds for one ingested paper (FR-LIT-2), each a list of normalized
    neighbour records. A kind S2 cannot serve stays empty and is logged.
    """
    fetch = fetch or get_json
    sid = _path_id(s2_id_for_ref(paper_ref))
    out: dict[str, list[dict]] = {
        "references": [],
        "citations": [],
        "recommendations": [],
    }
    for kind, url in (
        (
            "references",
            build_url(
                GRAPH_API, f"/paper/{sid}/references", fields=EDGE_FIELDS, limit=100
            ),
        ),
        (
            "citations",
            build_url(
                GRAPH_API, f"/paper/{sid}/citations", fields=EDGE_FIELDS, limit=100
            ),
        ),
        (
            "recommendations",
            build_url(REC_API, f"/papers/forpaper/{sid}", fields=EDGE_FIELDS, limit=50),
        ),
    ):
        try:
            body = fetch(url)
        except SemanticScholarError as exc:
            log.warning("S2 %s for %s unavailable: %s", kind, paper_ref, exc)
            continue
        if not isinstance(body, dict):
            log.warning("S2 %s for %s: unexpected shape", kind, paper_ref)
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


def fetch_recommendations(
    positive: list[str],
    negative: list[str],
    *,
    fields: str = SEARCH_FIELDS,
    limit: int = 100,
    post: Callable[[str, dict], object] | None = None,
) -> list[dict]:
    """
    Papers like ``positive`` and unlike ``negative`` (S2 ids, or ``ArXiv:``/``DOI:``
    forms): ``POST /recommendations/v1/papers/``. Raw S2 paper objects.
    """
    if not positive:
        return []
    post = post or post_json
    body = post(
        build_url(
            REC_API,
            "/papers/",
            fields=fields,
            limit=max(1, min(limit, RECOMMENDATIONS_MAX_LIMIT)),
        ),
        {"positivePaperIds": positive, "negativePaperIds": negative},
    )
    papers = body.get("recommendedPapers") if isinstance(body, dict) else None
    if not isinstance(papers, list):
        raise SemanticScholarError("recommendations response has no paper list")
    return [p for p in papers if isinstance(p, dict) and p.get("paperId")]
