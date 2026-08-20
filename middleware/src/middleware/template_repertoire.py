"""The protocol repertoire (FR-TPL): the corpus read as ranked design shapes."""

from __future__ import annotations

import logging
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from middleware import matching, template_registry
from middleware.db import CORPUS_STUDY_ID, Paper

log = logging.getLogger(__name__)

MIN_REFERENCE_CONFIDENCE = 0.5

RARE_SUPPORT_FLOOR = 3
RARE_ADMISSION_CONFIDENCE = 0.75

COMMON_SUPPORT = 100
ESTABLISHED_SUPPORT = 25


def design_signature(template: dict) -> list[str]:
    """The distinctive phrases a paper using this shape says about itself."""
    explicit = [
        str(p).strip().lower() for p in template.get("designSignature", []) or []
    ]
    if explicit:
        return [p for p in explicit if p]
    plan = template.get("statisticalPlan", {}) or {}
    fallback = {(template.get("designType") or "").replace("-", " ").strip()}
    fallback |= {
        str(e.get("test", "")).replace("-", " ").strip()
        for e in plan.get("perRQ", []) or []
    }
    return sorted(p.lower() for p in fallback if p)


def _signature_pattern(phrases: list[str]) -> re.Pattern[str] | None:
    """
    One alternation over every phrase in the repertoire, whole-token (so 'tlx' doesn't
    fire inside another word).
    """
    if not phrases:
        return None
    alternation = "|".join(re.escape(p) for p in sorted(phrases, key=len, reverse=True))
    return re.compile(rf"(?<![a-z0-9])({alternation})(?![a-z0-9])")


def scan_corpus(s: Session, signatures: dict[str, list[str]]) -> list[dict]:
    """
    One pass over the corpus, recording which signature phrases each paper carries.
    """
    pattern = _signature_pattern(
        sorted({phrase for phrases in signatures.values() for phrase in phrases})
    )
    if pattern is None:
        return []
    rows = s.execute(
        select(Paper.paper_ref, Paper.title, Paper.abstract, Paper.score).where(
            Paper.study_id == CORPUS_STUDY_ID
        )
    ).all()
    scanned = []
    for ref, title, abstract, score in rows:
        text = f"{title or ''} {abstract or ''}".lower()
        hits = sorted({m.group(1) for m in pattern.finditer(text)})
        if not hits:
            continue
        scanned.append(
            {
                "ref": ref,
                "title": title or "",
                "confidence": matching.paper_confidence(score),
                "phrases": hits,
            }
        )
    return scanned


def _declared_references(s: Session, template: dict) -> tuple[list[dict], list[str]]:
    """The papers the template itself cites, resolved against the corpus."""
    refs: list[dict] = []
    unresolved: list[str] = []
    for src in template.get("source", []) or []:
        ref = src.get("paperRef")
        if not ref:
            continue
        meta = matching.get_paper_metadata(s, ref)
        if meta is None:
            unresolved.append(ref)
            continue
        refs.append(
            {
                "ref": meta["ref"],
                "title": meta["title"],
                "year": meta["year"],
                "venue": meta["venue"],
                "confidence": meta["confidence"],
                "role": src.get("role", "source"),
                "matchReason": "Cited by this design as its source.",
            }
        )
    return refs, unresolved


def references_for(
    s: Session, template: dict, *, limit: int = 8, scanned: list[dict] | None = None
) -> dict:
    """Papers that used this design shape, declared sources first."""
    signature = design_signature(template)
    if scanned is None:
        scanned = scan_corpus(s, {"": signature})
    declared, unresolved = _declared_references(s, template)
    seen = {r["ref"] for r in declared}

    users = [
        paper
        for paper in scanned
        if paper["ref"] not in seen
        and (paper["confidence"] or 0.0) >= MIN_REFERENCE_CONFIDENCE
        and any(phrase in signature for phrase in paper["phrases"])
    ]
    users.sort(
        key=lambda p: (
            -len([x for x in p["phrases"] if x in signature]),
            -(p["confidence"] or 0.0),
            p["ref"],
        )
    )
    matched = [
        {
            "ref": p["ref"],
            "title": p["title"],
            "year": None,
            "venue": "",
            "confidence": p["confidence"],
            "role": "uses-this-design",
            "matchReason": "Describes itself with: "
            + ", ".join(sorted(x for x in p["phrases"] if x in signature)[:3])
            + ".",
        }
        for p in users[: max(limit - len(declared), 0)]
    ]
    return {
        "references": [*declared, *matched],
        "support": len(declared) + len(users),
        "phrases": signature,
        "unresolved": unresolved,
    }


def _band(support: int) -> str:
    if support >= COMMON_SUPPORT:
        return "common"
    if support >= ESTABLISHED_SUPPORT:
        return "established"
    return "rare"


def _admission(support: int, references: list[dict]) -> tuple[bool, str]:
    """Whether a rare design is well-sourced enough to be admitted."""
    if support >= RARE_SUPPORT_FLOOR:
        return True, ""
    best = max((r.get("confidence") or 0.0) for r in references) if references else 0.0
    if best >= RARE_ADMISSION_CONFIDENCE:
        return True, ""
    return False, (
        f"Seen in only {support} corpus paper(s), and the strongest of them "
        f"is {best:.2f} confidence — below the {RARE_ADMISSION_CONFIDENCE} "
        "a rare design needs to be proposed."
    )


# The repertoire is a pure function of (registry, corpus), and both change rarely —
# memoize on the corpus row count so a fresh import or an abstract backfill invalidates
# it, but repeated page loads don't re-rank 13 shapes.
_CACHE: dict[tuple, list[dict]] = {}


def rank_repertoire(
    s: Session, *, limit_refs: int = 6, use_cache: bool = True
) -> list[dict]:
    """Every design shape, ranked common → rare, with its references."""
    corpus_rows = s.scalar(
        select(func.count()).select_from(Paper).where(Paper.study_id == CORPUS_STUDY_ID)
    )
    key = (corpus_rows or 0, limit_refs)
    if use_cache and key in _CACHE:
        return _CACHE[key]

    templates = {
        meta["templateId"]: template_registry.load_template(meta["templateId"])
        for meta in template_registry.list_templates()
    }
    scanned = scan_corpus(
        s, {tid: design_signature(t) for tid, t in templates.items()}
    )

    entries: list[dict] = []
    for meta in template_registry.list_templates():
        template = templates[meta["templateId"]]
        found = references_for(s, template, limit=limit_refs, scanned=scanned)
        admitted, note = _admission(found["support"], found["references"])
        entries.append(
            {
                **meta,
                "id": meta["templateId"],
                "version": meta["templateVersion"],
                "support": found["support"],
                "signature": found["phrases"],
                "band": _band(found["support"]),
                "admitted": admitted,
                "admissionNote": note,
                "references": found["references"],
                "unresolvedSources": found["unresolved"],
            }
        )
    entries.sort(key=lambda e: (-e["support"], e["id"]))
    if use_cache:
        _CACHE[key] = entries
    return entries


def clear_cache() -> None:
    """Drop the memoized ranking (tests, and after a registry change)."""
    _CACHE.clear()
