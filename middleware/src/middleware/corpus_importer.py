"""Corpus importer."""

import json
import logging
import re
from pathlib import Path
from threading import Lock, Thread

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from middleware import paper_index, pdf
from middleware.db import (
    CORPUS_STUDY_ID,
    Paper,
    PaperEdge,
    get_engine,
    make_session_factory,
)

log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parent.parent.parent.parent
PAPERS_DIR = REPO / "docs" / "papers"
CORPUS_INDEX = PAPERS_DIR / "corpus-index.json"

VIA_EDGE_KIND = "harvested-via"

TIER_A_SEED_SCORE = 14.0

_EXPECTED_ROWS: int | None = None
_BOOTSTRAP_LOCK = Lock()
_BOOTSTRAP_THREAD: Thread | None = None
_BOOTSTRAP_STATE: dict[str, object] = {
    "state": "idle",
    "papers": 0,
    "expected": 0,
    "error": "",
}

_TIER_A_ROW = re.compile(
    r"^\|\s*`([^`]+)`\s*\|\s*(.+?)\s*\|\s*(\d{4})\s*\|\s*(.+?)\s*\|\s*$"
)
_MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def parse_tier_a() -> list[dict]:
    """Tier A seed metadata from the hand-curated README table."""
    text = (PAPERS_DIR / "README.md").read_text("utf-8")
    papers = []
    for line in text.splitlines():
        m = _TIER_A_ROW.match(line)
        if not m:
            continue
        stem, paper_cell, year, why = m.groups()
        if stem.lower() == "file":
            continue
        link = _MD_LINK.search(paper_cell)
        title = (link.group(1) if link else paper_cell).lstrip("★ ").strip()
        url = link.group(2) if link else ""
        arxiv_id = doi = ""
        if "arxiv.org/abs/" in url:
            arxiv_id = url.rsplit("/abs/", 1)[1].strip("/")
        elif "doi.org/" in url:
            doi = url.split("doi.org/", 1)[1].strip("/")
        papers.append(
            {
                "ref": f"corpus:{stem}",
                "title": title,
                "year": int(year),
                "why": why.strip(),
                "file": stem,
                "arxivId": arxiv_id,
                "doi": doi,
                "url": url,
            }
        )
    return papers


def parse_tier_b() -> list[dict]:
    """
    Tier B entries from the harvest index, metadata passed through verbatim (quality
    metrics per FR-LIT-8 F8.5 stay on the index file; the row keeps what the store
    models).
    """
    if not CORPUS_INDEX.exists():
        log.warning("corpus-index.json not found at %s", CORPUS_INDEX)
        return []
    data = json.loads(CORPUS_INDEX.read_text("utf-8"))
    return [e for e in data.get("tierB", []) if e.get("ref")]


def expected_corpus_rows() -> int:
    """The number of paper rows represented by the checked-in corpus manifest."""
    global _EXPECTED_ROWS
    if _EXPECTED_ROWS is None:
        _EXPECTED_ROWS = len(parse_tier_a()) + len(parse_tier_b())
    return _EXPECTED_ROWS


def corpus_status_for_session(s: Session) -> dict[str, object]:
    """Return an honest readiness status for the corpus-backed UI."""
    total = s.scalar(
        select(func.count())
        .select_from(Paper)
        .where(Paper.study_id == CORPUS_STUDY_ID)
    ) or 0
    expected = expected_corpus_rows()
    with _BOOTSTRAP_LOCK:
        state = dict(_BOOTSTRAP_STATE)
    if total >= expected > 0:
        state.update(state="ready", papers=total, expected=expected, error="")
    elif state.get("state") not in {"loading", "error"}:
        state.update(
            state="partial" if total else "empty", papers=total, expected=expected
        )
    else:
        state.update(papers=total, expected=expected)
    return state


def tier_a_body(paper: dict, abstract: str = "") -> str:
    """
    The searchable text for a seed: title + curator's why + the enriched abstract when
    one has landed + local PDF text when a ``docs/papers/<stem>.pdf`` exists (PDFs are
    gitignored; absent ones degrade to metadata-only, never fail).
    """
    parts = [paper["title"], paper["why"]]
    if abstract:
        parts.append(abstract)
    pdf_path = PAPERS_DIR / f"{paper['file']}.pdf"
    if pdf_path.exists():
        extracted = pdf.extract(pdf_path.read_bytes())
        if extracted["text"]:
            parts.append(extracted["text"])
    return "\n\n".join(parts)


MIN_REAL_ABSTRACT_CHARS = 200


def enriched_abstracts(s: Session) -> dict[str, str]:
    """Corpus refs that already carry a real (backfilled) abstract."""
    rows = s.execute(
        select(Paper.paper_ref, Paper.abstract).where(
            Paper.study_id == CORPUS_STUDY_ID,
            func.length(func.coalesce(Paper.abstract, "")) >= MIN_REAL_ABSTRACT_CHARS,
        )
    ).all()
    return dict(rows)


def _upsert_corpus_paper(s: Session, values: dict) -> None:
    """Upsert one corpus row, keeping the longer ``abstract``."""
    engine = get_engine()
    row = dict(study_id=CORPUS_STUDY_ID, added_at="", **values)
    if engine and engine.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as _pg_insert
        stmt = _pg_insert(Paper).values([row])
    else:
        from sqlalchemy.dialects.sqlite import insert as _sq_insert
        stmt = _sq_insert(Paper).values([row])
    update_set = {k: v for k, v in values.items() if k != "paper_ref"}
    if "abstract" in update_set:
        update_set["abstract"] = case(
            (
                func.length(func.coalesce(Paper.abstract, ""))
                > func.length(func.coalesce(stmt.excluded.abstract, "")),
                Paper.abstract,
            ),
            else_=stmt.excluded.abstract,
        )
    s.execute(
        stmt.on_conflict_do_update(
            index_elements=["study_id", "paper_ref"], set_=update_set
        )
    )


def import_tier_a(s: Session) -> dict[str, int]:
    """Land the Tier A seeds; returns ref -> FTS chunk count."""
    indexed: dict[str, int] = {}
    enriched = enriched_abstracts(s)
    for paper in parse_tier_a():
        _upsert_corpus_paper(
            s,
            {
                "paper_ref": paper["ref"],
                "title": paper["title"],
                "year": paper["year"],
                "abstract": paper["why"],
                "curator_note": paper["why"],
                "arxiv_id": paper["arxivId"],
                "doi": paper["doi"],
                "url": paper["url"],
                "item_type": "paper",
                "source": "docs/papers/README.md",
                "tier": "A",
                "score": TIER_A_SEED_SCORE,
            },
        )
        body = tier_a_body(paper, enriched.get(paper["ref"], ""))
        indexed[paper["ref"]] = paper_index.index_paper(
            s, paper["ref"], paper["title"], body
        )
    return indexed


def import_tier_b(s: Session, *, batch_size: int = 500) -> dict[str, int]:
    """Land the harvested Tier B rows + FTS entries + via-edges."""
    seed_by_arxiv = {p["arxivId"]: p["ref"] for p in parse_tier_a() if p["arxivId"]}
    enriched = enriched_abstracts(s)
    indexed: dict[str, int] = {}
    entries = parse_tier_b()
    for i, entry in enumerate(entries):
        ref = entry["ref"]
        arxiv_id = ref[6:] if ref.startswith("arxiv:") else ""
        doi = ref[4:] if ref.startswith("doi:") else ""
        _upsert_corpus_paper(
            s,
            {
                "paper_ref": ref,
                "title": entry.get("title", ""),
                "year": entry.get("year"),
                "venue": entry.get("venue") or "",
                "arxiv_id": arxiv_id,
                "doi": doi,
                "item_type": "paper",
                "source": "corpus-index.json (FR-LIT-8 harvest)",
                "s2_id": entry.get("s2PaperId", ""),
                "citation_count": entry.get("citationCount"),
                "tier": "B",
                "score": entry.get("score"),
            },
        )
        body = "\n\n".join(
            part
            for part in (
                entry.get("title", ""),
                entry.get("venue") or "",
                enriched.get(ref, ""),
            )
            if part
        )
        indexed[ref] = paper_index.index_paper(s, ref, entry.get("title", ""), body)
        for via in entry.get("via", []):
            src = seed_by_arxiv.get(via)
            if not src:
                continue
            _engine = get_engine()
            if _engine and _engine.dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import insert as _pg_insert
                edge_stmt = (
                    _pg_insert(PaperEdge)
                    .values([{
                        "study_id": CORPUS_STUDY_ID,
                        "src_ref": src,
                        "dst_ref": ref,
                        "kind": VIA_EDGE_KIND,
                        "dst_title": entry.get("title", ""),
                        "dst_year": entry.get("year"),
                        "dst_citation_count": entry.get("citationCount"),
                    }])
                    .on_conflict_do_nothing()
                )
            else:
                from sqlalchemy.dialects.sqlite import insert as _sq_insert
                edge_stmt = (
                    _sq_insert(PaperEdge)
                    .values(
                        study_id=CORPUS_STUDY_ID,
                        src_ref=src,
                        dst_ref=ref,
                        kind=VIA_EDGE_KIND,
                        dst_title=entry.get("title", ""),
                        dst_year=entry.get("year"),
                        dst_citation_count=entry.get("citationCount"),
                    )
                    .on_conflict_do_nothing(
                        index_elements=["study_id", "src_ref", "dst_ref", "kind"]
                    )
                )
            s.execute(edge_stmt)
        if (i + 1) % batch_size == 0:
            s.commit()
            log.info("Tier B: %d/%d landed", i + 1, len(entries))
    return indexed


def import_corpus(db_url: str, *, session_factory=None) -> dict:
    """One-shot, idempotent import of both tiers."""
    factory = session_factory or make_session_factory(db_url)
    with factory() as s:
        tier_a = import_tier_a(s)
        s.commit()
        tier_b = import_tier_b(s)
        s.commit()
    return {
        "tierA": {"count": len(tier_a), "chunks": sum(tier_a.values())},
        "tierB": {"count": len(tier_b), "chunks": sum(tier_b.values())},
    }


def start_background_import(db_url: str, session_factory) -> dict[str, object]:
    """Warm an empty/default database without delaying the first page response."""
    global _BOOTSTRAP_THREAD
    with _BOOTSTRAP_LOCK:
        if _BOOTSTRAP_THREAD is not None and _BOOTSTRAP_THREAD.is_alive():
            return dict(_BOOTSTRAP_STATE)

        with session_factory() as s:
            current = s.scalar(
                select(func.count())
                .select_from(Paper)
                .where(Paper.study_id == CORPUS_STUDY_ID)
            ) or 0
        expected = expected_corpus_rows()
        if current >= expected > 0:
            _BOOTSTRAP_STATE.update(
                state="ready", papers=current, expected=expected, error=""
            )
            return dict(_BOOTSTRAP_STATE)

        _BOOTSTRAP_STATE.update(
            state="loading", papers=current, expected=expected, error=""
        )

        def run() -> None:
            global _BOOTSTRAP_THREAD
            try:
                import_corpus(db_url, session_factory=session_factory)
                with session_factory() as s:
                    total = s.scalar(
                        select(func.count())
                        .select_from(Paper)
                        .where(Paper.study_id == CORPUS_STUDY_ID)
                    ) or 0
                with _BOOTSTRAP_LOCK:
                    _BOOTSTRAP_STATE.update(
                        state="ready" if total >= expected else "partial",
                        papers=total,
                        expected=expected,
                        error="",
                    )
            except Exception as exc:  # noqa: BLE001 - report startup health in the UI
                log.exception("background corpus import failed")
                with _BOOTSTRAP_LOCK:
                    _BOOTSTRAP_STATE.update(
                        state="error", papers=current, expected=expected, error=str(exc)
                    )
            finally:
                _BOOTSTRAP_THREAD = None

        _BOOTSTRAP_THREAD = Thread(
            target=run, name="phoenix-corpus-import", daemon=True
        )
        _BOOTSTRAP_THREAD.start()
        return dict(_BOOTSTRAP_STATE)


_DEMO_SEED_REFS = (
    "corpus:trust-in-ai-code-generation",
    "corpus:insecure-code-with-ai-assistants",
    "corpus:metr-early-2025-dev-productivity",
    "corpus:realhumaneval",
    "corpus:guidelines-empirical-llm-se",
)


def verify_import(db_url: str) -> dict[str, bool]:
    """
    Spot-check an import against the source files (F8.1/F8.4): demo seeds present and
    searchable, row counts match the index, via-edges landed.
    """
    factory = make_session_factory(db_url)
    expected_a = len(parse_tier_a())
    expected_b = len(parse_tier_b())
    checks: dict[str, bool] = {}
    with factory() as s:
        for ref in _DEMO_SEED_REFS:
            row = s.execute(
                select(Paper).where(
                    Paper.study_id == CORPUS_STUDY_ID, Paper.paper_ref == ref
                )
            ).scalar_one_or_none()
            checks[f"seed-row:{ref}"] = row is not None and row.tier == "A"
        count_a = s.scalar(
            select(func.count())
            .select_from(Paper)
            .where(Paper.study_id == CORPUS_STUDY_ID, Paper.tier == "A")
        )
        count_b = s.scalar(
            select(func.count())
            .select_from(Paper)
            .where(Paper.study_id == CORPUS_STUDY_ID, Paper.tier == "B")
        )
        checks["tier-a-count-matches-readme"] = count_a == expected_a
        checks["tier-b-count-matches-index"] = count_b == expected_b
        checks["corpus-floor-1000"] = (count_a + count_b) >= 1000
        edge_count = s.scalar(
            select(func.count())
            .select_from(PaperEdge)
            .where(
                PaperEdge.study_id == CORPUS_STUDY_ID, PaperEdge.kind == VIA_EDGE_KIND
            )
        )
        checks["via-edges-landed"] = (edge_count or 0) > 0
        hits = paper_index.search(s, "over-trust AI generated code", limit=10)
        found = {h["paperRef"] for h in hits}
        checks["fts-finds-demo-seeds"] = bool(
            found & {_DEMO_SEED_REFS[0], _DEMO_SEED_REFS[1]}
        )
    return checks
