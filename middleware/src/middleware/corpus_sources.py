"""
Turn arXiv and Semantic Scholar responses into one candidate shape, and decide whether
a candidate is already known. Pure functions: no network, no database.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV_NS = "{http://arxiv.org/schemas/atom}"
_VERSION = re.compile(r"v\d+$")
_ARXIV_DOI = re.compile(r"^10\.48550/arxiv\.(?P<id>.+)$", re.IGNORECASE)


class SourceFormatError(ValueError):
    """A source returned something that is not the documented shape."""


def _squash(text: str | None) -> str:
    return re.sub(r"\s+", " ", text).strip() if isinstance(text, str) else ""


def strip_version(arxiv_id: str) -> str:
    """``2610.07639v1`` -> ``2610.07639``; old-style ``cs/0112017v2`` too."""
    return _VERSION.sub("", arxiv_id.strip())


def title_key(title: str) -> str:
    """Case, punctuation and spacing-insensitive key for catching re-posted titles."""
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def canonical_ref(
    *, arxiv_id: str | None, doi: str | None, s2_id: str | None
) -> str | None:
    """
    The corpus's ref convention (see ``scripts/corpus_harvest.py``): ``arxiv:<id>`` when
    an arXiv id exists (including the 10.48550/arxiv.* DOIs), else ``doi:<doi>``,
    else ``s2:<paperId>``.
    """
    if arxiv_id:
        return f"arxiv:{strip_version(arxiv_id)}"
    if doi:
        match = _ARXIV_DOI.match(doi.strip())
        if match:
            return f"arxiv:{strip_version(match.group('id'))}"
        return f"doi:{doi.strip().lower()}"
    if s2_id:
        return f"s2:{s2_id}"
    return None


def parse_arxiv_atom(body: bytes) -> list[dict]:
    """Candidates from an arXiv API Atom feed. Refuses documents that declare a DTD."""
    declarations = body.replace(b"\x00", b"").upper()
    if b"<!DOCTYPE" in declarations or b"<!ENTITY" in declarations:
        raise SourceFormatError("arXiv response declares a DTD or entities; refused")
    try:
        root = ET.fromstring(body)  # noqa: S314 - DTD/entities refused above
    except ET.ParseError as exc:
        raise SourceFormatError(f"arXiv response is not valid XML: {exc}") from exc
    if root.tag != f"{_ATOM}feed":
        raise SourceFormatError("arXiv response is not an Atom feed")
    out = []
    for entry in root.findall(f"{_ATOM}entry"):
        raw_id = _squash(entry.findtext(f"{_ATOM}id"))
        arxiv_id = (
            strip_version(raw_id.rsplit("/abs/", 1)[-1]) if "/abs/" in raw_id else ""
        )
        title = _squash(entry.findtext(f"{_ATOM}title"))
        if not arxiv_id or not title:
            continue
        published = _squash(entry.findtext(f"{_ATOM}published"))[:10]
        out.append(
            {
                "ref": canonical_ref(arxiv_id=arxiv_id, doi=None, s2_id=None),
                "arxivId": arxiv_id,
                "doi": _squash(entry.findtext(f"{_ARXIV_NS}doi")).lower() or None,
                "s2Id": None,
                "title": title,
                "abstract": _squash(entry.findtext(f"{_ATOM}summary")),
                "year": int(published[:4]) if published[:4].isdigit() else None,
                "publishedAt": published or None,
                "venue": "arXiv",
                "authors": [
                    _squash(a.findtext(f"{_ATOM}name"))
                    for a in entry.findall(f"{_ATOM}author")
                ],
                "citationCount": None,
                "source": "arxiv",
                "url": f"https://arxiv.org/abs/{arxiv_id}",
            }
        )
    return out


def parse_s2_bulk(payload: dict) -> list[dict]:
    """Candidates from a Semantic Scholar ``/paper/search/bulk`` response."""
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise SourceFormatError("Semantic Scholar response has no 'data' list")
    out = []
    for paper in payload["data"]:
        if not isinstance(paper, dict):
            continue
        ids = paper.get("externalIds") or {}
        if not isinstance(ids, dict):
            ids = {}
        title = _squash(paper.get("title"))
        ref = canonical_ref(
            arxiv_id=ids.get("ArXiv"), doi=ids.get("DOI"), s2_id=paper.get("paperId")
        )
        if not title or ref is None:
            continue
        date = paper.get("publicationDate") or ""
        out.append(
            {
                "ref": ref,
                "arxivId": strip_version(ids["ArXiv"]) if ids.get("ArXiv") else None,
                "doi": (ids.get("DOI") or "").strip().lower() or None,
                "s2Id": paper.get("paperId"),
                "title": title,
                "abstract": _squash(paper.get("abstract")),
                "year": paper.get("year"),
                "publishedAt": date or None,
                "venue": _squash(paper.get("venue")),
                "authors": [
                    _squash(a.get("name"))
                    for a in paper.get("authors") or []
                    if a.get("name")
                ],
                "citationCount": paper.get("citationCount"),
                "source": "s2",
                "url": (
                    f"https://arxiv.org/abs/{strip_version(ids['ArXiv'])}"
                    if ids.get("ArXiv")
                    else (f"https://doi.org/{ids['DOI']}" if ids.get("DOI") else None)
                ),
            }
        )
    return out


def merge_sources(candidates: list[dict]) -> list[dict]:
    """
    One candidate per paper. arXiv metadata wins (CC0, with an abstract); Semantic
    Scholar fills what arXiv lacks (venue, citation count, DOI).
    """
    merged: dict[str, dict] = {}
    for cand in sorted(candidates, key=lambda c: c["source"] != "arxiv"):
        key = cand["ref"]
        if key not in merged:
            merged[key] = dict(cand)
            continue
        base = merged[key]
        for field in ("doi", "s2Id", "citationCount", "url"):
            if base.get(field) in (None, "") and cand.get(field) not in (None, ""):
                base[field] = cand[field]
        if base["venue"] in ("", "arXiv") and cand["venue"] not in ("", "arXiv"):
            base["venue"] = cand["venue"]
        if not base["abstract"] and cand["abstract"]:
            base["abstract"] = cand["abstract"]
    return list(merged.values())


def is_known(candidate: dict, known_refs: set[str], known_titles: set[str]) -> bool:
    """Already in the corpus or the candidate pool, by ref, or by normalised title."""
    return (
        candidate["ref"] in known_refs or title_key(candidate["title"]) in known_titles
    )
