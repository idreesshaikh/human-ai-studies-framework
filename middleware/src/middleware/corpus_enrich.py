"""Abstract backfill for the corpus (FR-LIT-8 quality, FR-LIT-9 matching)."""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from middleware import corpus_importer, paper_index, semantic_scholar
from middleware.corpus_importer import MIN_REAL_ABSTRACT_CHARS
from middleware.db import CORPUS_STUDY_ID, Paper, make_session_factory

log = logging.getLogger(__name__)

ENRICH_FIELDS = "abstract,externalIds"


def s2_id_for_row(row: Paper) -> str:
    """The id S2 can resolve this corpus row by, or "" if there is none."""
    if row.s2_id:
        return row.s2_id
    if row.doi:
        return f"DOI:{row.doi}"
    if row.arxiv_id:
        return f"ARXIV:{row.arxiv_id}"
    ref = row.paper_ref or ""
    if ref.startswith(("doi:", "arxiv:", "s2:")):
        return semantic_scholar.s2_id_for_ref(ref)
    return ""


def select_candidates(s: Session, *, limit: int | None = None) -> list[Paper]:
    """Corpus rows lacking a real abstract, highest confidence first."""
    stmt = (
        select(Paper)
        .where(
            Paper.study_id == CORPUS_STUDY_ID,
            func.length(func.coalesce(Paper.abstract, "")) < MIN_REAL_ABSTRACT_CHARS,
        )
        .order_by(Paper.score.desc().nullslast(), Paper.id)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(s.scalars(stmt))


def _searchable_body(row: Paper, seeds: dict[str, dict]) -> str:
    """The row's FTS body after enrichment."""
    seed = seeds.get(row.paper_ref)
    if seed is not None:
        return corpus_importer.tier_a_body(seed, row.abstract or "")
    parts = [row.venue or "", row.curator_note or "", row.abstract or ""]
    return "\n\n".join(p for p in parts if p)


def enrich_abstracts(
    db_url: str,
    *,
    limit: int | None = None,
    batch_size: int = semantic_scholar.BATCH_MAX_IDS,
    post=semantic_scholar.post_json,
) -> dict:
    """Backfill missing abstracts from S2, in batches."""
    factory = make_session_factory(db_url)
    summary = {
        "candidates": 0,
        "requested": 0,
        "enriched": 0,
        "unresolved": 0,
        "skipped_no_id": 0,
        "batches": 0,
    }
    with factory() as s:
        seeds = {p["ref"]: p for p in corpus_importer.parse_tier_a()}
        candidates = select_candidates(s, limit=limit)
        summary["candidates"] = len(candidates)
        ids = {row.paper_ref: s2_id_for_row(row) for row in candidates}
        askable = [row for row in candidates if ids[row.paper_ref]]
        summary["skipped_no_id"] = len(candidates) - len(askable)

        for start in range(0, len(askable), batch_size):
            chunk = askable[start : start + batch_size]
            refs = [row.paper_ref for row in chunk]
            try:
                found = semantic_scholar.fetch_papers_batch(
                    refs,
                    fields=ENRICH_FIELDS,
                    id_for_ref=lambda r: ids.get(r, ""),
                    post=post,
                )
            except semantic_scholar.SemanticScholarError as exc:
                # One bad batch must not lose the run's earlier progress - it is already
                # committed; report and carry on.
                log.warning("batch at %d failed (%s) - skipping", start, exc)
                continue
            summary["requested"] += len(chunk)
            summary["batches"] += 1
            for row in chunk:
                record = found.get(row.paper_ref)
                abstract = (record or {}).get("abstract") or ""
                if not abstract:
                    summary["unresolved"] += 1
                    continue
                row.abstract = abstract
                if not row.s2_id and record.get("s2Id"):
                    row.s2_id = record["s2Id"]
                paper_index.index_paper(
                    s, row.paper_ref, row.title or "", _searchable_body(row, seeds)
                )
                summary["enriched"] += 1
            s.commit()
            log.info(
                "corpus-enrich: %d/%d attempted, %d enriched",
                min(start + batch_size, len(askable)),
                len(askable),
                summary["enriched"],
            )
    return summary


def enrichment_status_for_session(s: Session) -> dict:
    """How much of the corpus carries a real abstract (the honest counter)."""
    total = s.scalar(
        select(func.count())
        .select_from(Paper)
        .where(Paper.study_id == CORPUS_STUDY_ID)
    )
    with_abstract = s.scalar(
        select(func.count())
        .select_from(Paper)
        .where(
            Paper.study_id == CORPUS_STUDY_ID,
            func.length(func.coalesce(Paper.abstract, ""))
            >= MIN_REAL_ABSTRACT_CHARS,
        )
    )
    return {
        "papers": total or 0,
        "withAbstract": with_abstract or 0,
        "missing": (total or 0) - (with_abstract or 0),
    }


def enrichment_status(db_url: str) -> dict:
    """
    CLI convenience: opens its own session (``__main__.py``'s ``corpus-enrich`` command
    runs outside any request scope).
    """
    factory = make_session_factory(db_url)
    with factory() as s:
        return enrichment_status_for_session(s)
