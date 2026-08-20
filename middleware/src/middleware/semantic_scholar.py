"""Semantic Scholar Graph API client (FR-LIT-1/2; decision D8)."""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

GRAPH_API = "https://api.semanticscholar.org/graph/v1"
REC_API = "https://api.semanticscholar.org/recommendations/v1"

_MIN_INTERVAL = 1.0
_pace_lock = threading.Lock()
_last_request = 0.0

PAPER_FIELDS = "title,authors,year,venue,abstract,externalIds,citationCount"
EDGE_FIELDS = "title,authors,year,externalIds,citationCount"

BATCH_MAX_IDS = 500

EDGE_CAP = 50


class SemanticScholarError(Exception):
    """S2 could not serve a request (surfaced as a warning; cached graph kept)."""


def _headers() -> dict[str, str]:
    key = os.environ.get("MIDDLEWARE_S2_API_KEY")
    return {"x-api-key": key} if key else {}


def _pace() -> None:
    """Hold every caller to S2's 1 req/s budget (cumulative, all endpoints)."""
    global _last_request
    with _pace_lock:
        wait = _MIN_INTERVAL - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()


def get_json(url: str, *, retries: int = 5) -> object:
    """
    GET, self-paced to the documented 1 req/s budget, honouring ``Retry-After`` with
    exponential fallback on a 429.
    """
    for attempt in range(retries):
        _pace()
        req = urllib.request.Request(url, headers=_headers())
        try:
            with urllib.request.urlopen(req, timeout=20) as res:
                return json.loads(res.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < retries - 1:
                retry_after = (exc.headers or {}).get("Retry-After", "")
                delay = float(retry_after) if retry_after.isdigit() else 2.0**attempt
                time.sleep(min(delay, 30.0))
                continue
            raise SemanticScholarError(f"GET {url} -> HTTP {exc.code}") from exc
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            raise SemanticScholarError(f"GET {url} failed: {exc}") from exc
    raise SemanticScholarError(f"GET {url} rate-limited after {retries} tries")


def post_json(url: str, payload: dict, *, retries: int = 5) -> object:
    """POST, sharing :func:`get_json`'s pacing and 429 posture."""
    body = json.dumps(payload).encode()
    headers = {**_headers(), "Content-Type": "application/json"}
    for attempt in range(retries):
        _pace()
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                return json.loads(res.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < retries - 1:
                retry_after = (exc.headers or {}).get("Retry-After", "")
                delay = float(retry_after) if retry_after.isdigit() else 2.0**attempt
                time.sleep(min(delay, 30.0))
                continue
            raise SemanticScholarError(f"POST {url} -> HTTP {exc.code}") from exc
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            raise SemanticScholarError(f"POST {url} failed: {exc}") from exc
    raise SemanticScholarError(f"POST {url} rate-limited after {retries} tries")


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
    """
    Canonical ``paperRef`` for an S2 paper object (matches the protocol scheme so links
    join): DOI first, else arXiv, else the S2 hash.
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


def fetch_paper(paper_ref: str, *, fetch=get_json) -> dict:
    """Metadata for one paper by ref (FR-LIT-1 id path)."""
    sid = urllib.parse.quote(s2_id_for_ref(paper_ref), safe=":")
    paper = fetch(f"{GRAPH_API}/paper/{sid}?fields={PAPER_FIELDS}")
    if not isinstance(paper, dict):
        raise SemanticScholarError(f"unexpected paper shape for {paper_ref!r}")
    return normalize_paper(paper)


def fetch_papers_batch(
    paper_refs: list[str],
    *,
    fields: str = PAPER_FIELDS,
    id_for_ref=s2_id_for_ref,
    post=post_json,
) -> dict[str, dict]:
    """Metadata for many papers in one call (``POST /paper/batch``)."""
    out: dict[str, dict] = {}
    url = f"{GRAPH_API}/paper/batch?fields={fields}"
    for start in range(0, len(paper_refs), BATCH_MAX_IDS):
        chunk = [r for r in paper_refs[start : start + BATCH_MAX_IDS] if id_for_ref(r)]
        if not chunk:
            continue
        results = post(url, {"ids": [id_for_ref(r) for r in chunk]})
        if not isinstance(results, list):
            raise SemanticScholarError(f"unexpected batch shape for {len(chunk)} ids")
        for ref, record in zip(chunk, results, strict=False):
            if isinstance(record, dict) and record.get("paperId"):
                out[ref] = normalize_paper(record)
    return out


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
    """
    The three edge kinds for one ingested paper (FR-LIT-2), each a list of normalized
    neighbour records.
    """
    sid = urllib.parse.quote(s2_id_for_ref(paper_ref), safe=":")
    out: dict[str, list[dict]] = {
        "references": [],
        "citations": [],
        "recommendations": [],
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
