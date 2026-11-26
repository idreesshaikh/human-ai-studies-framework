"""
Corpus curation: keep the searchable corpus complete, current and on-topic.

One explicit ``corpus-curate`` run does four things:

1. **Re-check metadata.** Corpus rows not checked for ``staleDays`` and every
   waiting candidate go to Semantic Scholar in batches. A run fills a missing
   abstract, sets a venue once a preprint is published, adds a DOI, refreshes
   the citation and influential-citation counts, re-scores the row (freshness
   decays as years pass), and stores the paper's SPECTER2 embedding.
2. **Fill abstracts from arXiv** where Semantic Scholar has none.
3. **Score topical relevance** as the mean cosine similarity of a paper's
   embedding to its ``neighbours`` nearest *human-chosen* papers: the README
   seeds, plus anything a person accepted or kept. Automatic decisions never
   become examples, so the corpus cannot drift by learning from itself.
4. **Triage** with cutoffs calibrated on the examples themselves (each seed's
   leave-one-out relevance), so the cutoffs move with the seed set:

   ``keep``    on-topic and sound
   ``review``  on-topic but weak (no abstract, old for its citations, closer to
               a rejected paper than to any example), or borderline but sound
   ``hidden``  off-topic, or borderline and weak

   Hidden rows leave search and matching but are never deleted. Seeds and
   human decisions are never changed by a run. Candidates that would be kept
   are admitted to the corpus; those that would be hidden are dismissed (an
   automatic, reversible status). Everything else waits in the review queue.
"""

from __future__ import annotations

import logging
import urllib.error
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from middleware import (
    corpus_enrich,
    corpus_fetchers,
    corpus_importer,
    corpus_refresh,
    corpus_scoring,
    paper_index,
    semantic_scholar,
)
from middleware.corpus_importer import MIN_REAL_ABSTRACT_CHARS, VIA_EDGE_KIND
from middleware.corpus_sources import (
    SourceFormatError,
    parse_arxiv_atom,
    strip_version,
)
from middleware.db import (
    CORPUS_STUDY_ID,
    CorpusCandidate,
    CorpusCurationRun,
    Paper,
    PaperEdge,
    PaperEmbedding,
)

log = logging.getLogger(__name__)

S2_FIELDS = (
    "title,abstract,venue,year,externalIds,citationCount,"
    "influentialCitationCount,embedding.specter_v2"
)
# An embedding makes each record roughly 15 kB of JSON; keep responses small.
S2_BATCH = 100
ARXIV_BATCH = 50
AUTO = "auto"
AUTO_DECIDER = "auto:curate"
PREPRINT_VENUES = frozenset({"", "arxiv", "arxiv.org"})
CURATIONS = ("keep", "review", "hidden")


class CurationError(RuntimeError):
    """A run cannot triage (for example, too few examples carry embeddings)."""


# --- relevance and triage (pure)


@dataclass(frozen=True)
class Cutoffs:
    keep_at: float
    hide_below: float
    basis: str


def _unit(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0, 1.0, norms)


def _top_k_mean(sims: np.ndarray, k: int) -> np.ndarray:
    k = max(1, min(k, sims.shape[1]))
    return np.sort(sims, axis=1)[:, -k:].mean(axis=1)


def leave_one_out(examples: np.ndarray, k: int) -> np.ndarray:
    """Each example's relevance to the *other* examples."""
    if len(examples) < 2:
        raise CurationError(
            "at least two examples are needed for leave-one-out scoring"
        )
    sims = examples @ examples.T
    np.fill_diagonal(sims, -np.inf)
    return _top_k_mean(sims, min(k, len(examples) - 1))


def calibrate(examples: np.ndarray, cfg: dict) -> Cutoffs:
    """Keep and hide cutoffs, from config when fixed, else from the examples."""
    if cfg.get("keepAt") is not None and cfg.get("hideBelow") is not None:
        return Cutoffs(
            float(cfg["keepAt"]), float(cfg["hideBelow"]), "fixed in curation config"
        )
    if len(examples) < 5:
        raise CurationError(
            f"only {len(examples)} example papers have embeddings; at least 5 "
            "are needed to calibrate (run without --dry-run to fetch them)"
        )
    loo = leave_one_out(examples, cfg["neighbours"])
    keep_at = float(np.percentile(loo, cfg["keepPercentile"]))
    return Cutoffs(
        round(keep_at, 4),
        round(keep_at - float(cfg["hideMargin"]), 4),
        f"{cfg['keepPercentile']:g}th percentile of {len(examples)} examples' "
        f"leave-one-out relevance, hide {cfg['hideMargin']:g} below",
    )


def weaknesses(
    *,
    abstract: str,
    year: int | None,
    citations: int | None,
    verifiable: bool,
    this_year: int,
) -> list[str]:
    """Plain-language reasons a paper is a weak entry, if any."""
    out = []
    if len((abstract or "").strip()) < MIN_REAL_ABSTRACT_CHARS:
        out.append("no abstract")
    if not verifiable:
        out.append("no DOI or arXiv id")
    age = corpus_scoring.age_citation_weakness(year, citations, this_year)
    if age:
        out.append(age)
    return out


def triage(
    *,
    relevance: float | None,
    nearest_example: float | None,
    nearest_counter: float | None,
    weak: list[str],
    cutoffs: Cutoffs,
) -> tuple[str, str]:
    """``(keep|review|hidden, reason)`` for one paper."""
    issues = list(weak)
    if (
        nearest_counter is not None
        and nearest_example is not None
        and nearest_counter > nearest_example
    ):
        issues.append("closer to a paper turned down than to any example")
    if relevance is None:
        reason = "no embedding to judge its topic"
        if issues:
            reason += "; " + "; ".join(issues)
        return "review", reason
    rel = f"relevance {relevance:.3f}"
    if relevance < cutoffs.hide_below:
        return "hidden", f"off-topic: {rel} is below {cutoffs.hide_below:.3f}"
    if relevance >= cutoffs.keep_at:
        if issues:
            return "review", f"on-topic ({rel}) but " + "; ".join(issues)
        return "keep", f"on-topic: {rel} is at least {cutoffs.keep_at:.3f}"
    if issues:
        return "hidden", f"borderline topic ({rel}) and " + "; ".join(issues)
    return "review", (
        f"borderline topic: {rel} is between {cutoffs.hide_below:.3f} "
        f"and {cutoffs.keep_at:.3f}"
    )


# --- embeddings


def _from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype="<f4")


def store_embedding(s: Session, ref: str, vector: list[float], now: str) -> bool:
    if not vector:
        return False
    try:
        values = np.asarray(vector, dtype="<f4")
    except (TypeError, ValueError, OverflowError):
        return False
    if values.ndim != 1 or not np.isfinite(values).all() or not np.any(values):
        return False
    if "curation_embedding_bytes" not in s.info:
        existing = s.scalar(select(PaperEmbedding.vector).limit(1))
        s.info["curation_embedding_bytes"] = (
            len(existing) if existing is not None else 0
        )
    expected = s.info["curation_embedding_bytes"]
    if expected and expected != values.nbytes:
        return False
    s.info["curation_embedding_bytes"] = values.nbytes
    row = s.scalar(select(PaperEmbedding).where(PaperEmbedding.ref == ref))
    if row is None:
        s.add(PaperEmbedding(ref=ref, vector=values.tobytes(), fetched_at=now))
    else:
        row.vector, row.fetched_at = values.tobytes(), now
    return True


def load_embeddings(s: Session) -> dict[str, np.ndarray]:
    return {
        ref: _from_blob(blob)
        for ref, blob in s.execute(select(PaperEmbedding.ref, PaperEmbedding.vector))
    }


# --- metadata refresh


def _batches(items: list, size: int) -> Iterable[list]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _published_venue(record: dict) -> str:
    venue = (record.get("venue") or "").strip()
    return "" if venue.lower() in PREPRINT_VENUES else venue


def _apply_to_row(row: Paper, rec: dict, now: str, stats: dict) -> bool:
    """Update one corpus row from an S2 record; True when its text changed."""
    text_changed = False
    abstract = (rec.get("abstract") or "").strip()
    # A seed's abstract column starts as its curator note ("why it's here").
    placeholder = row.tier == "A" and row.abstract == row.curator_note
    if len(abstract) >= MIN_REAL_ABSTRACT_CHARS and (
        placeholder or len((row.abstract or "").strip()) < MIN_REAL_ABSTRACT_CHARS
    ):
        row.abstract = abstract
        stats["abstractsFromS2"] += 1
        text_changed = True
    venue = _published_venue(rec)
    if venue and (row.venue or "").strip().lower() in PREPRINT_VENUES:
        row.venue = venue
        stats["venuesUpdated"] += 1
        text_changed = True
    ext = rec.get("externalIds") or {}
    doi = str(ext.get("DOI") or "").strip().lower()
    if doi and not row.doi and not doi.startswith("10.48550/"):
        row.doi = doi
    if row.year is None and rec.get("year"):
        row.year = rec["year"]
    row.s2_id = row.s2_id or rec.get("paperId") or ""
    if rec.get("citationCount") is not None:
        row.citation_count = rec["citationCount"]
    if rec.get("influentialCitationCount") is not None:
        row.influential_citation_count = rec["influentialCitationCount"]
    row.checked_at = now
    return text_changed


def _apply_to_candidate(cand: CorpusCandidate, rec: dict) -> None:
    abstract = (rec.get("abstract") or "").strip()
    if len(abstract) > len(cand.abstract or ""):
        cand.abstract = abstract
    venue = _published_venue(rec)
    if venue and (cand.venue or "").strip().lower() in PREPRINT_VENUES:
        cand.venue = venue
    cand.s2_id = cand.s2_id or rec.get("paperId")
    if rec.get("citationCount") is not None:
        cand.citation_count = rec["citationCount"]


def refresh_metadata(
    s: Session,
    rows: list[Paper],
    candidates: list[CorpusCandidate],
    *,
    post: Callable[[str, dict], object],
    now: str,
    stats: dict,
) -> set[str]:
    """
    Re-check rows and candidates against S2 in batches; returns the refs whose
    searchable text changed. A failing batch is reported and skipped.
    """
    targets = [
        (obj, semantic_scholar.lookup_id(obj.s2_id, obj.doi, obj.arxiv_id))
        for obj in [*rows, *candidates]
    ]
    for obj, lookup in targets:
        if not lookup and isinstance(obj, Paper):
            obj.checked_at = now
    targets = [(obj, lookup) for obj, lookup in targets if lookup]
    changed: set[str] = set()
    for chunk in _batches(targets, S2_BATCH):
        try:
            results = semantic_scholar.fetch_batch_raw(
                [lookup for _, lookup in chunk], fields=S2_FIELDS, post=post
            )
        except semantic_scholar.SemanticScholarError as exc:
            stats["errors"].append({"source": "s2-batch", "message": str(exc)[:300]})
            continue
        for (obj, _), rec in zip(chunk, results, strict=False):
            ref = obj.paper_ref if isinstance(obj, Paper) else obj.ref
            if rec is None:
                stats["unresolved"] += 1
                if isinstance(obj, Paper):
                    obj.checked_at = now
                continue
            stats["checked"] += 1
            if isinstance(obj, Paper):
                if _apply_to_row(obj, rec, now, stats):
                    changed.add(ref)
            else:
                _apply_to_candidate(obj, rec)
            vector = (rec.get("embedding") or {}).get("vector") or []
            if store_embedding(s, ref, vector, now):
                stats["embeddings"] += 1
        s.commit()
        log.info("corpus-curate: %d checked so far", stats["checked"])
    return changed


def backfill_from_arxiv(
    rows: list[Paper],
    *,
    fetch_ids: Callable[[list[str]], bytes],
    stats: dict,
) -> set[str]:
    """Abstracts S2 lacks, from the arXiv API (CC0 metadata)."""
    need = [
        r
        for r in rows
        if r.arxiv_id and len((r.abstract or "").strip()) < MIN_REAL_ABSTRACT_CHARS
    ]
    changed: set[str] = set()
    for chunk in _batches(need, ARXIV_BATCH):
        try:
            entries = parse_arxiv_atom(
                fetch_ids([strip_version(r.arxiv_id) for r in chunk])
            )
        except (OSError, urllib.error.URLError, SourceFormatError) as exc:
            stats["errors"].append({"source": "arxiv-ids", "message": str(exc)[:300]})
            continue
        by_id = {e["arxivId"]: e for e in entries}
        for row in chunk:
            entry = by_id.get(strip_version(row.arxiv_id))
            abstract = (entry or {}).get("abstract", "")
            if len(abstract) >= MIN_REAL_ABSTRACT_CHARS:
                row.abstract = abstract
                stats["abstractsFromArxiv"] += 1
                changed.add(row.paper_ref)
    return changed


def rescore(s: Session, rows: list[Paper], this_year: int) -> None:
    """Re-score harvested rows with fresh counts; freshness decays with the year."""
    rows = [r for r in rows if r.tier != "A"]
    if not rows:
        return
    edges = dict(
        s.execute(
            select(PaperEdge.dst_ref, func.count())
            .where(
                PaperEdge.study_id == CORPUS_STUDY_ID,
                PaperEdge.kind == VIA_EDGE_KIND,
                PaperEdge.dst_ref.in_([r.paper_ref for r in rows]),
            )
            .group_by(PaperEdge.dst_ref)
        ).all()
    )
    for row in rows:
        row.score = corpus_scoring.score(
            {
                "year": row.year,
                "citationCount": row.citation_count,
                "influentialCitationCount": row.influential_citation_count,
                "venue": row.venue,
                "openAccessPdf": bool(row.arxiv_id) or None,
            },
            edges.get(row.paper_ref, 0),
            this_year,
        )


# --- search visibility


def _reindex(s: Session, row: Paper, seeds: dict[str, dict]) -> None:
    if row.curation == "hidden":
        return
    paper_index.index_paper(
        s, row.paper_ref, row.title or "", corpus_enrich._searchable_body(row, seeds)
    )


def _set_curation(
    s: Session,
    row: Paper,
    decision: str,
    reason: str,
    by: str,
    seeds: dict[str, dict],
) -> bool:
    """Apply a decision; hidden rows leave the search index. True if it changed."""
    was = row.curation
    row.curation, row.curation_reason, row.curation_by = decision, reason, by
    if decision == "hidden" and was != "hidden":
        paper_index.deindex_paper(s, row.paper_ref)
    elif was == "hidden" and decision != "hidden":
        _reindex(s, row, seeds)
    return was != decision


# --- triage over the database


def _verifiable(ref: str, doi: str | None, arxiv_id: str | None) -> bool:
    return bool(doi or arxiv_id or ref.startswith(("doi:", "arxiv:")))


Measure = Callable[[str], tuple[float | None, float | None, float | None]]


def judge(
    vectors: dict[str, np.ndarray],
    positive: list[str],
    negative: list[str],
    cfg: dict,
) -> tuple[Measure, Cutoffs, int, int]:
    """
    ``measure(ref) -> (relevance, nearest example, nearest counter-example)`` over
    ``vectors``, and the cutoffs calibrated on the examples in the same space.
    """
    pos_refs = [r for r in positive if r in vectors]
    neg_refs = [r for r in negative if r in vectors]
    if not pos_refs:
        raise CurationError(
            "no example paper has an embedding yet (run without --dry-run to fetch)"
        )
    examples = _unit(np.stack([vectors[r] for r in pos_refs]))
    cutoffs = calibrate(examples, cfg)
    counters = _unit(np.stack([vectors[r] for r in neg_refs])) if neg_refs else None
    pos_index = {r: i for i, r in enumerate(pos_refs)}
    k = cfg["neighbours"]

    def measure(ref: str) -> tuple[float | None, float | None, float | None]:
        vec = vectors.get(ref)
        if vec is None:
            return None, None, None
        unit = _unit(vec[None, :])
        sims = (unit @ examples.T)[0]
        if ref in pos_index:  # an example is not its own neighbour
            sims = np.delete(sims, pos_index[ref])
        if not len(sims):
            return None, None, None
        top = float(_top_k_mean(sims[None, :], k)[0])
        counter = float((unit @ counters.T)[0].max()) if counters is not None else None
        return round(top, 4), float(sims.max()), counter

    return measure, cutoffs, len(pos_refs), len(neg_refs)


def decide_candidate(
    s: Session,
    cand: CorpusCandidate,
    measure: Measure,
    cutoffs: Cutoffs,
    *,
    this_year: int,
    now: str,
    basis: str = "",
    may_hide: bool = True,
) -> str:
    """
    Triage one waiting candidate: ``keep`` admits it to the corpus, ``hidden``
    dismisses it (automatic and reversible), ``review`` leaves it for a person.
    With ``may_hide`` false, a would-be dismissal is left for a person instead.
    """
    rel, nearest, counter = measure(cand.ref)
    decision, reason = triage(
        relevance=rel,
        nearest_example=nearest,
        nearest_counter=counter,
        weak=weaknesses(
            abstract=cand.abstract,
            year=cand.year,
            citations=cand.citation_count,
            verifiable=_verifiable(cand.ref, cand.doi, cand.arxiv_id),
            this_year=this_year,
        ),
        cutoffs=cutoffs,
    )
    if decision == "hidden" and not may_hide:
        decision = "review"
        reason = f"{reason}; left for a person: no validated dismissal cutoff here"
    if basis:
        reason = f"{reason} ({basis})"
    cand.relevance, cand.triage_reason = rel, reason
    if decision == "keep":
        corpus_refresh.promote(
            s, cand.ref, decided_by=AUTO_DECIDER, now=now, note=reason
        )
    elif decision == "hidden":
        cand.status, cand.decided_by, cand.decided_at, cand.note = (
            "dismissed",
            AUTO_DECIDER,
            now,
            reason,
        )
    else:
        cand.status, cand.decided_by, cand.decided_at = "new", None, None
    return decision


def triage_all(s: Session, cfg: dict, *, this_year: int, now: str) -> dict:
    """Score and triage every corpus row and waiting candidate."""
    vectors = load_embeddings(s)
    positive, negative = corpus_refresh.human_examples(s)
    measure, cutoffs, n_pos, n_neg = judge(vectors, positive, negative, cfg)

    seeds = {p["ref"]: p for p in corpus_importer.parse_tier_a()}
    moved = dict.fromkeys(CURATIONS, 0)
    for row in s.scalars(select(Paper).where(Paper.study_id == CORPUS_STUDY_ID)):
        rel, nearest, counter = measure(row.paper_ref)
        row.relevance = rel
        if row.tier == "A":
            if row.curation != "keep":
                reason = "seed listed in docs/papers/README.md"
                _set_curation(s, row, "keep", reason, "seed", seeds)
            continue
        if (row.curation_by or "").startswith(corpus_refresh.HUMAN):
            continue
        decision, reason = triage(
            relevance=rel,
            nearest_example=nearest,
            nearest_counter=counter,
            weak=weaknesses(
                abstract=row.abstract,
                year=row.year,
                citations=row.citation_count,
                verifiable=_verifiable(row.paper_ref, row.doi, row.arxiv_id),
                this_year=this_year,
            ),
            cutoffs=cutoffs,
        )
        if _set_curation(s, row, decision, reason, AUTO, seeds):
            moved[decision] += 1
    s.flush()

    tally = {"keep": 0, "review": 0, "hidden": 0}
    for cand in list(
        s.scalars(
            select(CorpusCandidate).where(
                (CorpusCandidate.status == "new")
                | (
                    (CorpusCandidate.status == "dismissed")
                    & (CorpusCandidate.decided_by == AUTO_DECIDER)
                )
            )
        )
    ):
        tally[
            decide_candidate(s, cand, measure, cutoffs, this_year=this_year, now=now)
        ] += 1
    s.flush()
    return {
        "cutoffs": {
            "keepAt": cutoffs.keep_at,
            "hideBelow": cutoffs.hide_below,
            "basis": cutoffs.basis,
            "examples": n_pos,
            "counterExamples": n_neg,
        },
        "moved": moved,
        "candidates": {
            "admitted": tally["keep"],
            "review": tally["review"],
            "dismissed": tally["hidden"],
        },
    }


def curation_counts(s: Session) -> dict[str, int]:
    """Corpus rows by curation state ("unscored" = not yet triaged)."""
    counts = {**dict.fromkeys(CURATIONS, 0), "unscored": 0}
    for state, n in s.execute(
        select(Paper.curation, func.count())
        .where(Paper.study_id == CORPUS_STUDY_ID)
        .group_by(Paper.curation)
    ):
        counts[state if state in CURATIONS else "unscored"] += n
    return counts


# --- one run


def _stale_rows(s: Session, *, cutoff: str, limit: int | None) -> list[Paper]:
    stmt = (
        select(Paper)
        .where(
            Paper.study_id == CORPUS_STUDY_ID,
            (func.coalesce(Paper.checked_at, "") == "") | (Paper.checked_at < cutoff),
        )
        .order_by((Paper.tier != "A"), Paper.score.desc().nulls_last(), Paper.paper_ref)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(s.scalars(stmt))


def _unembedded_candidates(s: Session) -> list[CorpusCandidate]:
    return list(
        s.scalars(
            select(CorpusCandidate).where(
                CorpusCandidate.status.in_(("new", "dismissed")),
                ~CorpusCandidate.ref.in_(select(PaperEmbedding.ref)),
            )
        )
    )


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(
    session_factory,
    *,
    config: dict,
    limit: int | None = None,
    dry_run: bool = False,
    today: date | None = None,
    now: Callable[[], str] = utc_now,
    post: Callable[[str, dict], object] | None = None,
    fetch_arxiv_ids: Callable[[list[str]], bytes] | None = None,
) -> dict:
    """
    One curation pass. ``dry_run`` makes no network calls and writes nothing:
    it previews the triage on the metadata already stored.
    """
    cfg = config.get("curation") or corpus_refresh.CURATION_DEFAULTS
    today = today or datetime.now(UTC).date()
    post = post or semantic_scholar.post_json
    fetch_arxiv_ids = fetch_arxiv_ids or corpus_fetchers.fetch_arxiv_by_ids
    stats = {
        "checked": 0,
        "unresolved": 0,
        "abstractsFromS2": 0,
        "abstractsFromArxiv": 0,
        "venuesUpdated": 0,
        "embeddings": 0,
        "errors": [],
    }
    started = now()
    with session_factory() as s:
        record = None
        if not dry_run:
            record = CorpusCurationRun(started_at=started, status="running")
            s.add(record)
            s.commit()
            cutoff = (
                datetime.fromisoformat(started.replace("Z", "+00:00"))
                - timedelta(days=cfg["staleDays"])
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            rows = _stale_rows(s, cutoff=cutoff, limit=limit)
            seeds = {p["ref"]: p for p in corpus_importer.parse_tier_a()}
            changed = refresh_metadata(
                s, rows, _unembedded_candidates(s), post=post, now=started, stats=stats
            )
            changed |= backfill_from_arxiv(rows, fetch_ids=fetch_arxiv_ids, stats=stats)
            rescore(s, rows, today.year)
            for row in rows:
                if row.paper_ref in changed:
                    _reindex(s, row, seeds)
            s.commit()
        try:
            outcome = triage_all(s, cfg, this_year=today.year, now=started)
            status = "partial" if stats["errors"] else "ok"
        except CurationError as exc:
            outcome = {"triageSkipped": str(exc)}
            status = "failed"
        result = {
            "status": "dry-run" if dry_run and status == "ok" else status,
            **stats,
            **outcome,
            "corpus": curation_counts(s),
            "candidateCounts": corpus_refresh.candidate_counts(s),
        }
        if dry_run:
            s.rollback()
        if record is not None:
            record.status, record.finished_at, record.summary = status, now(), result
            s.commit()
        return result


def last_run_summary(s: Session) -> dict | None:
    rec = s.scalar(
        select(CorpusCurationRun)
        .where(CorpusCurationRun.finished_at.is_not(None))
        .order_by(CorpusCurationRun.id.desc())
        .limit(1)
    )
    if rec is None:
        return None
    return {"finishedAt": rec.finished_at, "status": rec.status}


# --- human decisions and the review queue


def decide(
    s: Session, ref: str, *, accept: bool, decided_by: str, now: str, note: str = ""
) -> dict:
    """
    A person's decision on a candidate or a corpus row. It is sticky (runs never
    override it) and becomes an example or counter-example for later runs.
    """
    cand = s.scalar(select(CorpusCandidate).where(CorpusCandidate.ref == ref))
    if cand is not None and cand.status != "accepted":
        if accept:
            return corpus_refresh.promote(
                s, ref, decided_by=decided_by, now=now, note=note
            )
        return corpus_refresh.reject(s, ref, decided_by=decided_by, now=now, note=note)
    row = s.scalar(
        select(Paper).where(Paper.study_id == CORPUS_STUDY_ID, Paper.paper_ref == ref)
    )
    if row is None:
        raise KeyError(ref)
    if row.tier == "A" and not accept:
        raise ValueError(
            f"{ref} is a seed; remove it from docs/papers/README.md instead"
        )
    seeds = {p["ref"]: p for p in corpus_importer.parse_tier_a()}
    _set_curation(
        s,
        row,
        "keep" if accept else "hidden",
        note or ("kept by hand" if accept else "hidden by hand"),
        f"{corpus_refresh.HUMAN}{decided_by}",
        seeds,
    )
    s.flush()
    return {"ref": ref, "status": row.curation}


def review_queue(s: Session, *, limit: int = 50) -> list[dict]:
    """Corpus rows and candidates waiting for a person, most relevant first."""
    rows = [
        {
            "kind": "corpus",
            "ref": r.paper_ref,
            "title": r.title,
            "year": r.year,
            "venue": r.venue,
            "relevance": r.relevance,
            "reason": r.curation_reason,
        }
        for r in s.scalars(
            select(Paper).where(
                Paper.study_id == CORPUS_STUDY_ID, Paper.curation == "review"
            )
        )
    ]
    rows += [
        {
            "kind": "candidate",
            "ref": c.ref,
            "title": c.title,
            "year": c.year,
            "venue": c.venue,
            "relevance": c.relevance,
            "reason": c.triage_reason or "not yet triaged",
        }
        for c in s.scalars(
            select(CorpusCandidate).where(CorpusCandidate.status == "new")
        )
    ]
    rows.sort(key=lambda r: (r["relevance"] is None, -(r["relevance"] or 0), r["ref"]))
    return rows[: max(1, limit)]


def format_summary(result: dict) -> str:
    """The text the CLI prints after a run."""
    lines = [f"corpus curation {result['status']}"]
    if result.get("checked") or result.get("unresolved"):
        lines.append(
            f"  metadata: {result['checked']} re-checked, "
            f"{result['unresolved']} unknown to Semantic Scholar, "
            f"{result['embeddings']} embeddings stored"
        )
        lines.append(
            f"  filled: {result['abstractsFromS2']} abstracts from Semantic Scholar, "
            f"{result['abstractsFromArxiv']} from arXiv; "
            f"{result['venuesUpdated']} preprints now show their venue"
        )
    if "cutoffs" in result:
        c = result["cutoffs"]
        lines.append(
            f"  cutoffs: keep at {c['keepAt']:.3f}, hide below {c['hideBelow']:.3f} "
            f"({c['basis']}; {c['counterExamples']} counter-examples)"
        )
        m = result["moved"]
        lines.append(
            f"  this run moved {m['keep']} rows to keep, {m['review']} to review, "
            f"{m['hidden']} to hidden"
        )
        cd = result["candidates"]
        lines.append(
            f"  candidates: {cd['admitted']} admitted, {cd['review']} waiting for "
            f"review, {cd['dismissed']} dismissed"
        )
    else:
        lines.append(f"  triage skipped: {result.get('triageSkipped', '')}")
    t = result["corpus"]
    lines.append(
        f"  corpus now: {t['keep']} keep, {t['review']} review, {t['hidden']} hidden, "
        f"{t['unscored']} not yet triaged"
    )
    for err in result["errors"]:
        lines.append(f"  ! {err['source']}: {err['message']}")
    return "\n".join(lines)
