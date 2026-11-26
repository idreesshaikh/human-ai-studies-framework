"""Idea → paper matching (FR-LIT-9): the ladder behind recommendation cards."""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from middleware import corpus_scoring, paper_index
from middleware.corpus_importer import VIA_EDGE_KIND
from middleware.db import CORPUS_STUDY_ID, Paper, PaperEdge

log = logging.getLogger(__name__)

_STOPWORDS = frozenset(
    [
        "that",
        "this",
        "with",
        "from",
        "what",
        "were",
        "they",
        "have",
        "been",
        "does",
        "their",
        "study",
        "using",
        "about",
        "would",
        "could",
        "paper",
        "papers",
        "research",
        "the",
        "and",
        "for",
        "are",
        "is",
        "to",
        "in",
        "of",
        "on",
        "or",
        "as",
        "an",
        "be",
        "do",
        "how",
        "can",
        "you",
        "my",
        "we",
        "it",
        "will",
        "want",
        "think",
        "one",
        "know",
        "not",
        "sure",
        "dont",
        "don",
        "t",
        "maybe",
        "just",
        "which",
        "should",
        "use",
        "make",
        "more",
        "less",
        "than",
        "whether",
        "people",
        "person",
        "participants",
        "participant",
        "session",
        "sessions",
        "task",
        "tasks",
        "condition",
        "conditions",
        "compare",
        "comparison",
        "design",
        "method",
        "methods",
        "measure",
        "measures",
        "measuring",
        "result",
        "results",
        "effect",
        "effects",
    ]
)

# These words describe the broad application area, but are too common to justify
# calling a paper a direct match for a particular study. A recommendation titled
# "code" is not evidence about novice developers, productivity, workload, or bug
# fixing merely because the query also contains the word "code".
_GENERIC_MATCH_TERMS = frozenset(
    {
        "ai",
        "artificial",
        "intelligence",
        "code",
        "coding",
        "program",
        "programming",
        "software",
        "developer",
        "developers",
        "tool",
        "tools",
        "llm",
        "llms",
        "model",
        "models",
        "generative",
        "computer",
    }
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

# Live search (``match_papers(live=True)``) runs only when fewer than this many
# local results are strong: direct matches on at least LIVE_STRONG_TERMS specific
# terms. LIVE_TERMS caps the specific terms sent to Semantic Scholar.
LIVE_MIN_STRONG = 3
LIVE_STRONG_TERMS = 2
LIVE_TERMS = 6


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
    hidden = set(
        s.scalars(
            select(Paper.paper_ref).where(
                Paper.study_id == CORPUS_STUDY_ID,
                Paper.curation == "hidden",
                Paper.paper_ref.in_(list(votes)),
            )
        )
    )
    for ref in hidden:
        del votes[ref]
    for entry in votes.values():
        entry["score"] = WEIGHT_GRAPH_VOTE * min(entry["votes"], GRAPH_VOTE_CAP)
    ranked = sorted(votes.values(), key=lambda e: (-e["score"], e["ref"]))
    return ranked[:limit]


def _live_query(query: str) -> str:
    """
    A short keyword query for Semantic Scholar's relevance search: the query's most
    repeated specific terms (a long chat context repeats its topic), plus up to two
    broad ones to keep the search in the developer/AI domain. Empty when the query
    has no specific term, since a broad-only search would not find evidence.
    """
    words = [
        w
        for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]{1,}", query.lower())
        if w not in _STOPWORDS
    ]
    counts = Counter(words)
    order = {w: i for i, w in reversed(list(enumerate(words)))}
    ranked = sorted(counts, key=lambda w: (-counts[w], order[w]))
    specific = [w for w in ranked if w not in _GENERIC_MATCH_TERMS][:LIVE_TERMS]
    if not specific:
        return ""
    broad = [w for w in ranked if w in _GENERIC_MATCH_TERMS][:2]
    return " ".join(specific + broad)


def _annotate(
    candidate: dict,
    *,
    title: str,
    abstract: str,
    confidence: float | None,
    query_terms: list[str],
) -> dict:
    """Score and explain one candidate from its title and abstract (local or live)."""
    evidence_terms = _matched_terms(query_terms, f"{title} {abstract}")
    title_matches = _matched_terms(query_terms, title)
    specific_terms = [t for t in evidence_terms if t not in _GENERIC_MATCH_TERMS]
    # A paper that matches only broad coding vocabulary is never a direct match.
    # It may still be useful as adjacent reading, but it must not be presented as
    # evidence for a study just because the query contains the word "code".
    direct = bool(specific_terms)
    candidate["score"] = (
        candidate.get("score", 0.0)
        # Direct language evidence is deliberately separated from source quality.
        # This makes ranking explainable and prevents a famous, generic paper from
        # crowding out a less-cited but on-topic one.
        + (8.0 if direct else 0.0)
        + WEIGHT_MATCHED_TERM * len(evidence_terms)
        + len(title_matches)
        + WEIGHT_CONFIDENCE * (confidence if confidence is not None else 0.0)
    )
    candidate["matchKind"] = "direct" if direct else "adjacent"
    candidate["matchedTerms"] = (specific_terms or evidence_terms)[:5]
    if direct:
        location = "its title" if title_matches else "its abstract"
        candidate["matchReason"] = (
            f"Matches your study vocabulary in {location}: "
            f"{', '.join(candidate['matchedTerms'][:4])}."
        )
    return candidate


def _is_strong(candidate: dict) -> bool:
    return (
        candidate.get("matchKind") == "direct"
        and len(candidate.get("matchedTerms", [])) >= LIVE_STRONG_TERMS
    )


def needs_live(results: list[dict], limit: int) -> bool:
    """Whether local results are too few or too weak to skip a live search."""
    strong = sum(1 for c in results[:limit] if _is_strong(c))
    return strong < min(LIVE_MIN_STRONG, limit)


def _live_candidates(
    s: Session, query: str, query_terms: list[str], *, have: set[str]
) -> list[dict]:
    """Direct matches from a live Semantic Scholar search the corpus lacked."""
    from middleware import corpus_live

    keywords = _live_query(query)
    if not keywords:
        return []
    this_year = datetime.now(UTC).year

    def judged(rec: dict) -> dict:
        conf = paper_confidence(corpus_scoring.candidate_score(rec, this_year))
        cand = _annotate(
            {"ref": rec["ref"], "rung": "live", "score": 0.0},
            title=rec["title"],
            abstract=rec.get("abstract") or "",
            confidence=conf,
            query_terms=query_terms,
        )
        cand["confidence"] = conf
        return cand

    # A live result must earn its place (and its corpus row) with specific evidence.
    found = corpus_live.search(
        s.get_bind(), keywords, keep=lambda rec: judged(rec)["matchKind"] == "direct"
    )
    out = []
    for rec in found:
        if rec["ref"] in have:
            continue
        cand = judged(rec)
        conf = cand["confidence"]
        cand.update(
            title=rec["title"],
            authors=rec.get("authors") or [],
            year=rec.get("year"),
            venue=_display_venue(rec.get("venue")),
            identifier=(
                f"doi:{rec['doi']}"
                if rec.get("doi")
                else (f"arXiv:{rec['arxivId']}" if rec.get("arxivId") else "")
            ),
            abstract=(rec.get("abstract") or "").strip()[:480],
            inStudy=False,
            confidence=conf,
            source="semantic-scholar" if not rec.get("inCorpus") else "corpus",
        )
        have.add(rec["ref"])
        out.append(cand)
    return out


def match_papers(
    s: Session,
    query: str,
    *,
    study_id: str | None = None,
    limit: int = 5,
    use_llm: bool = False,
    expand: bool = False,
    live: bool = False,
) -> list[dict]:
    """
    Run the ladder and return enriched recommendations (FR-LIT-9).

    Matching makes no model call: the design chat's model quota is one request per
    researcher message. ``use_llm`` and ``expand`` are accepted for existing callers
    and ignored. With ``live=True``, a query the corpus answers weakly (fewer than
    :data:`LIVE_MIN_STRONG` direct matches on at least :data:`LIVE_STRONG_TERMS`
    specific terms) also asks Semantic Scholar, within
    :data:`corpus_live.LIVE_BUDGET_S`; new papers join the corpus. When S2 is slow,
    rate-limited or down, the local results come back unchanged.
    """
    del use_llm, expand
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
        if row is None or row.curation == "hidden":
            continue
        conf = paper_confidence(row.score)
        candidate.update(
            title=row.title,
            authors=row.authors or [],
            year=row.year,
            venue=_display_venue(row.venue),
            identifier=_public_identifier(row),
            abstract=(row.abstract or "").strip()[:480],
            inStudy=candidate["ref"] in study_refs,
            confidence=conf,
            source="corpus",
        )
        _annotate(
            candidate,
            title=row.title or "",
            abstract=row.abstract or "",
            confidence=conf,
            query_terms=query_terms,
        )
        if "matchReason" not in candidate:
            if candidate.get("via") and not candidate["matchedTerms"]:
                candidate["matchReason"] = _graph_reason(s, candidate)
            else:
                broad = ", ".join(
                    (candidate["matchedTerms"] or ["the coding topic"])[:4]
                )
                candidate["matchReason"] = f"Adjacent work shares broad terms: {broad}."
        enriched.append(candidate)

    # Graph-only results are useful adjacent reading, but the recommendation
    # rail must always prefer papers whose title or abstract answers the query.
    def order(items: list[dict]) -> list[dict]:
        return sorted(
            items,
            key=lambda c: (
                c.get("matchKind") != "direct",
                -c.get("score", 0.0),
                c["ref"],
            ),
        )

    enriched = order(enriched)
    if live and needs_live(enriched, limit):
        have = {c["ref"] for c in enriched} | study_refs
        enriched = order(
            [*enriched, *_live_candidates(s, query, query_terms, have=have)]
        )
    return [
        {
            "ref": c["ref"],
            "title": c.get("title", ""),
            "authors": c.get("authors", []),
            "year": c.get("year"),
            "venue": c.get("venue", ""),
            "identifier": c.get("identifier", ""),
            "abstract": c.get("abstract", ""),
            "inStudy": c.get("inStudy", False),
            "confidence": c.get("confidence"),
            "matchKind": c.get("matchKind", "adjacent"),
            "matchedTerms": c.get("matchedTerms", []),
            "matchReason": c.get("matchReason", ""),
            "source": c.get("source", "corpus"),
        }
        for c in enriched[:limit]
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


def _graph_reason(s: Session, candidate: dict) -> str:
    """An honest reason for a graph-only match: the seeds that vouch for it."""
    via = sorted(set(candidate.get("via", [])))
    titles = list(
        s.scalars(
            select(Paper.title).where(
                Paper.study_id == CORPUS_STUDY_ID, Paper.paper_ref.in_(via)
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
        return _live_metadata(paper_ref)
    return {
        "ref": row.paper_ref,
        "title": row.title,
        "year": row.year,
        "venue": row.venue or "",
        "confidence": paper_confidence(row.score),
        "why": row.abstract,
    }


def _live_metadata(paper_ref: str) -> dict | None:
    """A paper live search just returned whose corpus row has not landed yet."""
    from middleware import corpus_live

    rec = corpus_live.recent(paper_ref)
    if rec is None:
        return None
    score = corpus_scoring.candidate_score(rec, datetime.now(UTC).year)
    return {
        "ref": rec["ref"],
        "title": rec["title"],
        "year": rec.get("year"),
        "venue": rec.get("venue") or "",
        "confidence": paper_confidence(score),
        "why": rec.get("abstract") or "",
    }
