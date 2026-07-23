"""Idea → paper matching (FR-LIT-9): the ladder behind recommendation cards.

The ladder, each rung optional and degrading to the one below (spec
`fr-lit.md` §2):

1. **LLM rerank** - reorders and phrases one-line reasons for papers the
   lower rungs already retrieved (cite-what-you-were-given: the model never
   adds a paper). Runs only when a Mistral key is configured (D32); any
   failure falls through silently to rung 2's ordering.
2. **FTS relevance** - BM25 over title+abstract+extracted text
   (``paper_index``). Reasons are the matched terms (F9.2's requirement).
3. **Seed connectivity** - pure graph, no text: Tier A seeds whose
   title/why match the query terms vouch for their harvested neighbours
   (the ``harvested-via`` edges the corpus importer landed).

Every recommendation carries ``ref``, ``title``, ``confidence`` and a
``matchReason`` that is *kept* on ingest (elicitation evidence, FR-LIT-9.3).
"""

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

#: Words too generic to count as evidence of a match.
_STOPWORDS = frozenset(
    "that this with from what were they have been does their study using "
    "about would could paper papers research the and for are".split()
)

#: Ranking weights (autonomy charter: internals are free, constants live in
#: one named place). A paper's final score combines how *often* FTS surfaced
#: it (reciprocal-rank sum over its chunks), how many of the researcher's
#: own terms its title/why carry, and its continuous quality *confidence*
#: (from the harvest score) - so a high-merit harvested paper can outrank a
#: hand-curated seed instead of the tier deciding it categorically.
WEIGHT_MATCHED_TERM = 1.5
WEIGHT_CONFIDENCE = 2.0
#: Confidence maps a harvest quality score to 0..1 through a logistic centred
#: on the Tier B corpus median (10.6) with a spread near its stdev (2.0),
#: which opens up the compressed 8.85-21.7 score band. A paper with no score
#: reads as "unrated" (None), never a fabricated number.
_CONF_MIDPOINT = 10.6
_CONF_SCALE = 2.0


def paper_confidence(score: float | None) -> float | None:
    """Continuous 0..1 quality confidence for a paper, replacing the binary
    Tier A/B hierarchy as the thing that ranks and labels groundings."""
    if score is None:
        return None
    return round(1.0 / (1.0 + math.exp(-(score - _CONF_MIDPOINT) / _CONF_SCALE)), 3)
#: The graph rung is the *floor* of the ladder - it must never outrank text
#: evidence, so its votes are capped and scaled well under one FTS hit.
WEIGHT_GRAPH_VOTE = 0.15
GRAPH_VOTE_CAP = 5
#: A seed vouches for its neighbours only when the idea genuinely overlaps
#: it (two content terms), not on a single generic word.
GRAPH_SEED_MIN_TERMS = 2


def _terms(text: str) -> list[str]:
    """Content-bearing query terms, order-stable, de-duplicated."""
    seen: dict[str, None] = {}
    for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]{2,}", text.lower()):
        if t not in _STOPWORDS:
            seen.setdefault(t, None)
    return list(seen)


def _matched_terms(query_terms: list[str], text: str) -> list[str]:
    low = (text or "").lower()
    return [t for t in query_terms if t in low]


# ------------------------------------------------------- rung 2: FTS


def search_by_fts(s: Session, query: str, *, limit: int = 10) -> list[dict]:
    """BM25-ranked papers, aggregated per paper by reciprocal-rank sum over
    a deep chunk window - so a long PDF surfacing many chunks can't crowd
    single-chunk papers out of the candidate set."""
    hits = paper_index.search(s, query, limit=max(50, limit * 10))
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


# ------------------------------------------- rung 3: seed connectivity


def search_by_connectivity(s: Session, query: str, *, limit: int = 10) -> list[dict]:
    """Graph-only rung: seeds matching the query terms vouch for their
    harvested neighbours; a paper connected to more matching seeds ranks
    higher. Works with zero extracted text (offline floor)."""
    terms = _terms(query)
    if not terms:
        return []
    # Seeds are the papers that vouched for harvested neighbours — i.e. the
    # sources of harvested-via edges — not a provenance tier. This keeps the
    # connectivity rung working with the tier system removed from ranking.
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


# ------------------------------------------------- rung 1: LLM rerank


def rerank_with_llm(query: str, candidates: list[dict]) -> list[dict] | None:
    """Reorder ``candidates`` and phrase one-line reasons via Mistral.

    Cite-what-you-were-given: the model sees only the candidate list and may
    only return refs from it; anything else is dropped. Returns ``None`` on
    any failure or when no key is configured - the caller keeps rung 2's
    ordering (NFR-4: degrade, never block)."""
    from middleware import assistant

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


# ------------------------------------------------------- the full ladder


def match_papers(
    s: Session,
    query: str,
    *,
    study_id: str | None = None,
    limit: int = 5,
    use_llm: bool = True,
) -> list[dict]:
    """Run the ladder and return enriched recommendations (FR-LIT-9).

    Each: ``{ref, title, year, venue, inStudy, confidence, matchReason}``. The
    paper's provenance (A/B) or 'study' when it is already in ``study_id``'s
    paper set - the card renders the badge always-visible."""
    query_terms = _terms(query)
    fts = search_by_fts(s, query, limit=limit * 2)
    graph = search_by_connectivity(s, query, limit=limit * 2)
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
            continue  # never recommend a paper we don't hold (honesty)
        conf = paper_confidence(row.score)
        candidate.update(
            title=row.title,
            year=row.year,
            venue=row.venue,
            # No provenance tier: quality is the continuous `confidence`; the
            # only remaining distinction is whether the paper is already in the
            # researcher's study library.
            inStudy=candidate["ref"] in study_refs,
            confidence=conf,
        )
        matched = _matched_terms(query_terms, f"{row.title} {row.abstract}")
        candidate["score"] = (
            candidate.get("score", 0.0)
            + WEIGHT_MATCHED_TERM * len(matched)
            + WEIGHT_CONFIDENCE * (conf if conf is not None else 0.0)
        )
        if "matchReason" not in candidate:
            candidate["matchReason"] = _reason_for(query_terms, candidate, row)
        enriched.append(candidate)

    enriched.sort(key=lambda c: -c.get("score", 0.0))
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
            "inStudy": c.get("inStudy", False),
            "confidence": c.get("confidence"),
            "matchReason": c.get("matchReason", ""),
        }
        for c in results
    ]


def _reason_for(query_terms: list[str], candidate: dict, row: Paper) -> str:
    """A deterministic, honest reason: the matched terms (F9.2), or the
    vouching seeds for a graph-only match."""
    matched = _matched_terms(
        query_terms, f"{row.title} {row.abstract} {candidate.get('snippet', '')}"
    )
    if matched:
        return f"Matches your terms: {', '.join(matched[:4])}."
    via = candidate.get("via", [])
    if via:
        seeds = ", ".join(v.removeprefix("corpus:") for v in sorted(set(via))[:3])
        return f"Cited alongside the seed paper(s): {seeds}."
    return "Related in the corpus graph."


# --------------------------------------------- grounding lookups (FR-CONV-2)


def get_paper_metadata(s: Session, paper_ref: str) -> dict | None:
    """One paper's metadata for grounding chips - corpus scope first, so
    ``corpus:<slug>`` refs resolve for every study. Returns ``None`` for a
    paper the platform does not hold: grounding is retrieved, then claimed,
    never invented (FR-CONV-2.2)."""
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
