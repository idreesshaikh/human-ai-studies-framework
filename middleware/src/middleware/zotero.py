"""Zotero collection import (FR-LIT-5; decision D9; roadmap/09 item 2).

Reads one Zotero collection - the study's curated reading list - into the
study's paper set. Local-first like the rest of the stack (NFR-5): the
Zotero desktop app mirrors the web API v3 read-only on
``localhost:23119/api`` (no key, no rate limit, no page cap); when it is
not running we fall back to the hosted API at ``api.zotero.org``
(``MIDDLEWARE_ZOTERO_USER_ID`` + ``MIDDLEWARE_ZOTERO_API_KEY``). Both
speak the same JSON, so one normalizer covers both paths.

Items are normalized to paper records keyed by canonical ``paperRef``
(``doi:...``, else ``arxiv:...``, else ``zotero:<item key>``) - the same
identifier scheme the protocol's ``literature:`` list uses - so imported
papers join protocol links by construction, and re-imports are idempotent
on ``(studyId, paperRef)`` like every other ingest (FR-ING-2 discipline).
Only the collection's top-level items are read; attachments, notes, and
annotations are skipped, never stored.

This lands papers in FR-LIT-1's storage surface, not its full ingest
path: PDF/DOI extraction and Semantic Scholar enrichment arrive with
MP-10 and extend the same rows.
"""

import json
import re
import urllib.request

WEB_API = "https://api.zotero.org"
#: The desktop app's local read-only mirror of the web API (Zotero >= 7);
#: its single library is always user 0.
LOCAL_USER_PATH = "/api/users/0"
#: Web-API page cap. The local API has no cap and may answer one oversized
#: page; ``_get_paged`` stops on any page that is not exactly this size.
PAGE = 100

_ARXIV_ID = r"\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?"
_ARXIV_TAGGED = re.compile(rf"(?i)\barxiv:\s*({_ARXIV_ID})")
_ARXIV_URL = re.compile(rf"(?i)arxiv\.org/(?:abs|pdf)/({_ARXIV_ID})")
#: arXiv registers a DataCite DOI of this shape for every preprint; it must
#: canonicalize to the arXiv ref so a Zotero entry carrying it joins a
#: protocol that cites ``arxiv:<id>`` (and vice versa).
_ARXIV_DOI = re.compile(rf"(?i)^10\.48550/arxiv\.({_ARXIV_ID})$")
_DOI_EXTRA = re.compile(r"(?im)^\s*DOI:\s*(10\.\S+)")
_YEAR = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")

#: Zotero item types that are not papers.
SKIP_TYPES = {"attachment", "note", "annotation"}


class ZoteroError(Exception):
    """Zotero could not serve the collection (surfaced as HTTP 502)."""


class ZoteroUnreachable(ZoteroError):
    """Connection-level failure - the only case that triggers web fallback."""


def _get_json(url: str, headers: dict[str, str]) -> object:
    req = urllib.request.Request(
        url, headers={"Zotero-API-Version": "3", **headers}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return json.loads(res.read())
    except OSError as exc:  # URLError/HTTPError/timeout/refused
        raise ZoteroUnreachable(f"GET {url} failed: {exc}") from exc


def _get_paged(base: str, path: str, headers: dict[str, str]) -> list[dict]:
    """Follow ``start``/``limit`` pagination; one round trip on the local API."""
    out: list[dict] = []
    start = 0
    while True:
        batch = _get_json(f"{base}{path}?limit={PAGE}&start={start}", headers)
        if not isinstance(batch, list):
            raise ZoteroError(f"unexpected response shape from {base}{path}")
        out.extend(batch)
        if len(batch) != PAGE:
            return out
        start += PAGE


def _collection_key(collections: list[dict], wanted: str) -> str:
    """Resolve a collection key or (case-insensitive) name to its key."""
    by_name: dict[str, str] = {}
    for coll in collections:
        key = coll.get("key", "")
        if key == wanted:
            return key
        name = str(coll.get("data", {}).get("name", ""))
        by_name.setdefault(name.casefold(), key)
    if key := by_name.get(wanted.casefold()):
        return key
    names = ", ".join(sorted(n for n in by_name if n)) or "none"
    raise ZoteroError(
        f"no Zotero collection named or keyed {wanted!r} (available: {names})"
    )


def _read(base: str, headers: dict[str, str], collection: str) -> list[dict]:
    collections = _get_paged(base, "/collections", headers)
    key = _collection_key(collections, collection)
    return _get_paged(base, f"/collections/{key}/items/top", headers)


def fetch_collection_items(
    collection: str,
    *,
    local_url: str,
    user_id: str | None = None,
    api_key: str | None = None,
) -> tuple[list[dict], str]:
    """One collection's top-level items: local API first, web fallback.

    Returns ``(raw Zotero items, "local" | "web")``. A reachable local
    Zotero that lacks the collection does NOT fall back - the local API
    mirrors the same library, so the actionable error is the name list.
    """
    try:
        items = _read(f"{local_url.rstrip('/')}{LOCAL_USER_PATH}", {}, collection)
        return items, "local"
    except ZoteroUnreachable as exc:
        if not (user_id and api_key):
            raise ZoteroError(
                f"local Zotero API unreachable ({exc}) and no web fallback "
                "configured: set MIDDLEWARE_ZOTERO_USER_ID and "
                "MIDDLEWARE_ZOTERO_API_KEY"
            ) from exc
        headers = {"Zotero-API-Key": api_key}
        return _read(f"{WEB_API}/users/{user_id}", headers, collection), "web"


def _authors(data: dict) -> list[str]:
    creators = data.get("creators", [])
    authors = [c for c in creators if c.get("creatorType") == "author"] or creators
    out = []
    for c in authors:
        name = c.get("name") or " ".join(
            part for part in (c.get("firstName"), c.get("lastName")) if part
        )
        if name:
            out.append(name)
    return out


def _venue(data: dict) -> str:
    for field in (
        "publicationTitle", "proceedingsTitle", "conferenceName",
        "repository", "publisher",
    ):
        if data.get(field):
            return str(data[field])
    return ""


def _doi(data: dict) -> str:
    doi = str(data.get("DOI") or "").strip()
    if not doi:
        m = _DOI_EXTRA.search(str(data.get("extra") or ""))
        doi = m.group(1) if m else ""
    return doi.removeprefix("https://doi.org/").removeprefix("http://doi.org/")


def _arxiv(data: dict) -> str:
    for text, pattern in (
        (data.get("archiveID"), _ARXIV_TAGGED),
        (data.get("extra"), _ARXIV_TAGGED),
        (data.get("url"), _ARXIV_URL),
    ):
        if text and (m := pattern.search(str(text))):
            return m.group(1)
    return ""


def _year(data: dict) -> int | None:
    m = _YEAR.search(str(data.get("date") or ""))
    return int(m.group(1)) if m else None


def normalize_item(item: dict) -> dict | None:
    """One raw Zotero item -> one paper record; None for non-papers."""
    data = item.get("data", {})
    item_type = str(data.get("itemType", ""))
    if item_type in SKIP_TYPES:
        return None
    doi = _doi(data)
    arxiv_id = _arxiv(data)
    # An arXiv DataCite DOI is really an arXiv id: prefer the arXiv ref so it
    # joins a protocol that cites `arxiv:<id>`; keep the DOI in its field.
    if not arxiv_id and (m := _ARXIV_DOI.match(doi)):
        arxiv_id = m.group(1)
    if doi and not _ARXIV_DOI.match(doi):
        paper_ref = f"doi:{doi}"
    elif arxiv_id:
        paper_ref = f"arxiv:{arxiv_id}"
    elif doi:
        paper_ref = f"doi:{doi}"
    else:
        paper_ref = f"zotero:{item.get('key', '')}"
    return {
        "paperRef": paper_ref,
        "title": str(data.get("title", "")),
        "authors": _authors(data),
        "year": _year(data),
        "venue": _venue(data),
        "abstract": str(data.get("abstractNote", "")),
        "doi": doi,
        "arxivId": arxiv_id,
        "url": str(data.get("url", "")),
        "itemType": item_type,
        "zoteroKey": str(item.get("key", "")),
    }
