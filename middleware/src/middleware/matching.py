"""Idea → paper matching (FR-LIT-9): the ladder behind recommendation cards."""

from __future__ import annotations

import json
import logging
import math
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from middleware import paper_index
from middleware.corpus_importer import VIA_EDGE_KIND
from middleware.db import CORPUS_STUDY_ID, Paper, PaperEdge

log = logging.getLogger(__name__)

_STOPWORDS = frozenset(
    [
        "that", "this", "with", "from", "what", "were", "they", "have",
        "been", "does", "their", "study", "using", "about", "would",
        "could", "paper", "papers", "research", "the", "and", "for", "are",
        "is", "to", "in", "of", "on", "or", "as", "an", "be", "do",
        "how", "can", "you", "my", "we", "it", "will", "want", "think",
        "which", "should", "use", "make", "more", "less", "than", "whether",
        "people", "person", "participants", "participant", "session", "sessions",
        "task", "tasks", "condition", "conditions", "compare", "comparison",
        "design", "method", "methods", "measure", "measures", "measuring",
        "result", "results", "effect", "effects",
    ]
)

WEIGHT_MATCHED_TERM = 1.5
# Source quality is a tie-breaker, never a substitute for relevance. A highly
# cited survey should not outrank a direct match just because its corpus score
# is strong.
WEIGHT_CONFIDENCE = 0.35
# A paper with no score reads as "unrated" (None), never a fabricated number.
_CONF_MIDPOINT = 10.6
_CONF_SCALE = 2.0


def paper_confidence(score: float | None) -> float | None:
    """
    Continuous 0..1 quality confidence for a paper, replacing the binary Tier A/B
    hierarchy as the thing that ranks and labels groundings.
    """
    if score is None:
        return None
    return round(1.0 / (1.0 + math.exp(-(score - _CONF_MIDPOINT) / _CONF_SCALE)), 3)
# The graph rung is the *floor* of the ladder - it must never outrank text evidence, so
# its votes are capped and scaled well under one FTS hit.
WEIGHT_GRAPH_VOTE = 0.15
GRAPH_VOTE_CAP = 5
GRAPH_SEED_MIN_TERMS = 2


def _terms(text: str) -> list[str]:
    """Content-bearing query terms, order-stable, de-duplicated."""
    seen: dict[str, None] = {}
    for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]{1,}", text.lower()):
        if t not in _STOPWORDS:
            seen.setdefault(t, None)
    return list(seen)


def _matched_terms(query_terms: list[str], text: str) -> list[str]:
    """Return query terms present as words, not arbitrary substrings.

    Substring evidence made a short conversational fragment such as ``let``
    match the ``let`` inside ``completion``. That was both a ranking signal and
    the explanation printed to researchers, so unrelated papers could look
    confidently matched. Keep a small plural tolerance while preserving word
    boundaries.
    """
    tokens = set(re.findall(r"[A-Za-z0-9][A-Za-z0-9-]{1,}", (text or "").lower()))
    matched: list[str] = []
    for term in query_terms:
        if term in tokens or (
            term.endswith("s") and len(term) > 3 and term[:-1] in tokens
        ):
            matched.append(term)
    return matched


def search_by_fts(s: Session, query: str, *, limit: int = 10) -> list[dict]:
    """
    BM25-ranked papers, aggregated per paper by reciprocal-rank sum over a deep chunk
    window - so a long PDF surfacing many chunks can't crowd single-chunk papers out of
    the candidate set.
    """
    # Search the same content-bearing vocabulary used for ranking. Passing the
    # raw conversational sentence lets filler words and accidental fragments
    # decide which papers enter the candidate pool in the first place.
    search_terms = _terms(query)
    if not search_terms:
        return []
    hits = paper_index.search(s, " ".join(search_terms), limit=max(50, limit * 10))
    by_ref: dict[str, dict] = {}
    for rank, hit in enumerate(hits):
        ref = hit["paperRef"]
        entry = by_ref.setdefault(
            ref,
            {
                "ref": ref,
                "snippet": hit.get("snippet", ""),
                "score": 0.0,
                "rung": "fts",
            },
        )
        entry["score"] += 1.0 / (rank + 1)
    ranked = sorted(by_ref.values(), key=lambda e: (-e["score"], e["ref"]))
    return ranked[:limit]


def search_by_connectivity(s: Session, query: str, *, limit: int = 10) -> list[dict]:
    """
    Graph-only rung: seeds matching the query terms vouch for their harvested
    neighbours; a paper connected to more matching seeds ranks higher.
    """
    terms = _terms(query)
    if not terms:
        return []
    seeds = s.execute(
        select(Paper.paper_ref, Paper.title, Paper.abstract)
        .where(Paper.study_id == CORPUS_STUDY_ID)
        .where(
            Paper.paper_ref.in_(
                select(PaperEdge.src_ref)
                .where(
                    PaperEdge.study_id == CORPUS_STUDY_ID,
                    PaperEdge.kind == VIA_EDGE_KIND,
                )
                .distinct()
            )
        )
    ).all()
    matching_seeds = {
        ref
        for ref, title, why in seeds
        if len(_matched_terms(terms, f"{title} {why}")) >= GRAPH_SEED_MIN_TERMS
    }
    if not matching_seeds:
        return []
    votes: dict[str, dict] = {}
    for edge in s.scalars(
        select(PaperEdge).where(
            PaperEdge.study_id == CORPUS_STUDY_ID,
            PaperEdge.kind == VIA_EDGE_KIND,
            PaperEdge.src_ref.in_(matching_seeds),
        )
    ):
        entry = votes.setdefault(
            edge.dst_ref,
            {"ref": edge.dst_ref, "votes": 0, "via": [], "rung": "graph"},
        )
        entry["votes"] += 1
        entry["via"].append(edge.src_ref)
    for entry in votes.values():
        entry["score"] = WEIGHT_GRAPH_VOTE * min(entry["votes"], GRAPH_VOTE_CAP)
    ranked = sorted(votes.values(), key=lambda e: (-e["score"], e["ref"]))
    return ranked[:limit]


def rerank_with_llm(query: str, candidates: list[dict]) -> list[dict] | None:
    """Reorder ``candidates`` and phrase one-line reasons via Mistral."""
    from middleware import assistant

    # Paper ranking is part of the assistant's visible reasoning trail. Use the
    # the same EU Mistral route as the design turn, with the knowledge model's
    # larger context budget for citation-heavy reranking.
    client = assistant.make_client()
    if client is None or not candidates:
        return None
    menu = "\n".join(f"- {c['ref']}: {c.get('title', '')}" for c in candidates)
    prompt = (
        "A researcher described a study idea. Rank the following papers by "
        "relevance to it and give a one-line reason each. Reply with a JSON "
        'array of {"ref", "reason"}; use only refs from the list.\n\n'
        f"Idea: {query}\n\nPapers:\n{menu}"
    )
    try:
        res = client.post(
            client.base_url,
            {
                "model": client.model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "max_tokens": 1024,
            },
            {"Authorization": f"Bearer {client.api_key}"},
        )
        content = (res.get("choices") or [{}])[0].get("message", {}).get("content", "")
        parsed = json.loads(content)
        items = parsed if isinstance(parsed, list) else parsed.get("ranking", [])
    except Exception as exc:  # noqa: BLE001 - any provider failure degrades
        log.warning("LLM rerank unavailable, using FTS order: %s", exc)
        return None
    by_ref = {c["ref"]: c for c in candidates}
    ranked = []
    for item in items:
        ref = item.get("ref") if isinstance(item, dict) else None
        if ref in by_ref and by_ref[ref] not in ranked:
            entry = dict(by_ref[ref])
            reason = str(item.get("reason", "")).strip()
            if reason:
                entry["matchReason"] = reason
            entry["rung"] = "llm"
            ranked.append(entry)
    return ranked or None


_EXPANSION_CACHE: dict[str, str] = {}
_EXPANSION_MAX = 512


def expand_query(query: str) -> str:
    """
    Bridge vocabulary gaps for keyword FTS by asking the LLM for the concepts and
    synonyms a paper on this topic might use  -  the *semantic meaning* layer over the
    inverted index, now searching real abstracts (``corpus-enrich``) rather than titles
    alone.
    """
    q = query.strip()
    if not q:
        return q
    if q in _EXPANSION_CACHE:
        return _EXPANSION_CACHE[q]
    from middleware import assistant

    client = assistant.make_client()
    if client is None:
        return q
    prompt = (
        "A researcher described a study idea. List 6-10 concise search keywords "
        "and close synonyms a paper on this topic might use  -  comma-separated, "
        "no explanation.\n\nIdea: " + q
    )
    try:
        res = client.post(
            client.base_url,
            {
                "model": client.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 120,
            },
            {"Authorization": f"Bearer {client.api_key}"},
        )
        msg = (res.get("choices") or [{}])[0].get("message", {})
        extra = msg.get("content", "") or ""
        expanded = (q + " " + extra.replace("\n", " ")).strip()[:_EXPANSION_MAX]
    except Exception as exc:  # noqa: BLE001 - degrade to the raw query
        log.warning("query expansion unavailable, using raw query: %s", exc)
        expanded = q
    _EXPANSION_CACHE[q] = expanded
    return expanded


def match_papers(
    s: Session,
    query: str,
    *,
    study_id: str | None = None,
    limit: int = 5,
    use_llm: bool = True,
    expand: bool = True,
) -> list[dict]:
    """Run the ladder and return enriched recommendations (FR-LIT-9)."""
    search_query = expand_query(query) if expand else query
    query_terms = _terms(query)
    fts = search_by_fts(s, search_query, limit=limit * 2)
    graph = search_by_connectivity(s, search_query, limit=limit * 2)
    combined: list[dict] = []
    seen: set[str] = set()
    for candidate in [*fts, *graph]:
        if candidate["ref"] not in seen:
            seen.add(candidate["ref"])
            combined.append(candidate)

    study_refs: set[str] = set()
    if study_id:
        study_refs = {
            ref
            for (ref,) in s.execute(
                select(Paper.paper_ref).where(Paper.study_id == study_id)
            )
        }

    enriched = []
    for candidate in combined:
        row = s.execute(
            select(Paper).where(
                Paper.study_id == CORPUS_STUDY_ID,
                Paper.paper_ref == candidate["ref"],
            )
        ).scalar_one_or_none()
        if row is None and candidate["ref"] in study_refs:
            row = s.execute(
                select(Paper).where(
                    Paper.study_id == study_id,
                    Paper.paper_ref == candidate["ref"],
                )
            ).scalar_one_or_none()
        if row is None:
            continue
        conf = paper_confidence(row.score)
        candidate.update(
            title=row.title,
            year=row.year,
            venue=_display_venue(row.venue),
            identifier=_public_identifier(row),
            inStudy=candidate["ref"] in study_refs,
            confidence=conf,
        )
        matched = _matched_terms(query_terms, f"{row.title} {row.abstract}")
        title_matches = _matched_terms(query_terms, row.title)
        expanded_matches = _matched_terms(
            _terms(search_query), f"{row.title} {row.abstract}"
        )
        evidence_terms = list(dict.fromkeys([*matched, *expanded_matches]))
        direct = bool(evidence_terms)
        candidate["score"] = (
            candidate.get("score", 0.0)
            # Direct language evidence is deliberately separated from source
            # quality. This makes ranking explainable and prevents a famous,
            # generic paper from crowding out a less-cited but on-topic one.
            + (8.0 if direct else 0.0)
            + WEIGHT_MATCHED_TERM * len(evidence_terms)
            + len(title_matches)
            + WEIGHT_CONFIDENCE * (conf if conf is not None else 0.0)
        )
        candidate["matchKind"] = "direct" if direct else "adjacent"
        candidate["matchedTerms"] = evidence_terms[:5]
        if "matchReason" not in candidate:
            candidate["matchReason"] = _reason_for(
                s, query_terms, candidate, row, matched_terms=evidence_terms
            )
        enriched.append(candidate)

    # Graph-only results are useful adjacent reading, but the recommendation
    # rail must always prefer papers whose title or abstract answers the query.
    enriched.sort(
        key=lambda c: (
            c.get("matchKind") != "direct",
            -c.get("score", 0.0),
            c["ref"],
        )
    )
    if use_llm:
        reranked = rerank_with_llm(query, enriched)
        if reranked is not None:
            enriched = reranked
    results = enriched[:limit]
    return [
        {
            "ref": c["ref"],
            "title": c.get("title", ""),
            "year": c.get("year"),
            "venue": c.get("venue", ""),
            "identifier": c.get("identifier", ""),
            "inStudy": c.get("inStudy", False),
            "confidence": c.get("confidence"),
            "matchKind": c.get("matchKind", "adjacent"),
            "matchedTerms": c.get("matchedTerms", []),
            "matchReason": c.get("matchReason", ""),
        }
        for c in results
    ]


def _display_venue(venue: str | None) -> str:
    """Turn source metadata into a reader-facing venue label."""
    value = (venue or "").strip()
    if value.lower() in {"arxiv.org", "arxiv", "arx iv"}:
        return "arXiv preprint"
    return value


def _public_identifier(row: Paper) -> str:
    """Prefer a stable scholarly identifier; never expose a corpus slug."""
    if row.doi:
        return f"doi:{row.doi.removeprefix('doi:')}"
    if row.arxiv_id:
        return f"arXiv:{row.arxiv_id.removeprefix('arxiv:')}"
    if not row.paper_ref.startswith("corpus:"):
        return row.paper_ref
    return ""


def _reason_for(
    s: Session,
    query_terms: list[str],
    candidate: dict,
    row: Paper,
    *,
    matched_terms: list[str] | None = None,
) -> str:
    """
    A deterministic, honest reason: the matched terms (F9.2), or the vouching seeds for
    a graph-only match.
    """
    matched = matched_terms or _matched_terms(
        query_terms, f"{row.title} {row.abstract} {candidate.get('snippet', '')}"
    )
    if matched:
        title_terms = _matched_terms(query_terms, row.title)
        location = "its title" if title_terms else "its abstract"
        return f"Direct match in {location}: {', '.join(matched[:4])}."
    via = sorted(set(candidate.get("via", [])))
    if via:
        titles = list(
            s.scalars(
                select(Paper.title).where(
                    Paper.study_id == CORPUS_STUDY_ID,
                    Paper.paper_ref.in_(via),
                )
            )
        )
        if titles:
            shown = ", ".join(titles[:2])
            suffix = " and another paper" if len(titles) > 2 else ""
            return f"Adjacent to {shown}{suffix} through the library graph."
    return "Adjacent work surfaced through the library graph."


def get_paper_metadata(s: Session, paper_ref: str) -> dict | None:
    """
    One paper's metadata for grounding chips - corpus scope first, so ``corpus:<slug>``
    refs resolve for every study.
    """
    row = s.execute(
        select(Paper).where(
            Paper.study_id == CORPUS_STUDY_ID, Paper.paper_ref == paper_ref
        )
    ).scalar_one_or_none()
    if row is None:
        row = (
            s.execute(
                select(Paper).where(Paper.paper_ref == paper_ref).order_by(Paper.id)
            )
            .scalars()
            .first()
        )
    if row is None:
        return None
    return {
        "ref": row.paper_ref,
        "title": row.title,
        "year": row.year,
        "venue": row.venue or "corpus",
        "confidence": paper_confidence(row.score),
        "why": row.abstract,
    }
