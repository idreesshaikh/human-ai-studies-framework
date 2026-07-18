"""Corpus importer (MP-15 slice 2; the FR-LIT-8 importer named "pending").

Loads the hand-curated Tier A seeds (``docs/papers/README.md``) and the
harvested Tier B corpus (``docs/papers/corpus-index.json``) into the
middleware's paper store: ``Paper(tier=A|B)`` rows under the reserved
``platform-corpus`` study scope, FTS entries for retrieval, and the
seed-connectivity graph (Tier B ``via`` trails as ``paper_edges`` rows) that
backs the FR-LIT-9 match ladder's bottom rung. F8.4's fit criterion is
exactly this landing.

Refs are canonical and stable:

- Tier A seeds index under ``corpus:<file-stem>`` - the slug the specs,
  the design stub, and template ``source`` lists already cite - with the
  arXiv/DOI id kept in the row's metadata columns.
- Tier B entries keep the harvest's own ref (``arxiv:...``/``doi:...``),
  every one independently verifiable at the Semantic Scholar API (F8.1).

Honesty invariants (FR-LIT-8): nothing synthesized - a Tier A paper's FTS
body is its title + curator's "why" + local PDF text when present; a Tier B
body is the title (+ venue) the harvest recorded. Idempotent: Paper rows
upsert on (study_id, paper_ref); FTS entries are delete-then-insert; edges
insert-or-ignore. Re-running after a corpus update is the whole story.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from middleware import paper_index, pdf
from middleware.db import CORPUS_STUDY_ID, Paper, PaperEdge, make_session_factory

log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parent.parent.parent.parent
PAPERS_DIR = REPO / "docs" / "papers"
CORPUS_INDEX = PAPERS_DIR / "corpus-index.json"

#: Edge kind for a Tier B paper's discovery trail (``via`` seeds). Distinct
#: from the S2 'references'/'citations' kinds so the constellation can style
#: provenance edges differently.
VIA_EDGE_KIND = "harvested-via"

#: Tier A table row: | `file-stem` | [Title](url) - authors | Year | Why |
_TIER_A_ROW = re.compile(
    r"^\|\s*`([^`]+)`\s*\|\s*(.+?)\s*\|\s*(\d{4})\s*\|\s*(.+?)\s*\|\s*$"
)
_MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def parse_tier_a() -> list[dict]:
    """Tier A seed metadata from the hand-curated README table.

    Returns ``{ref, title, year, why, file, arxivId, doi, url}`` per seed,
    with ``ref = corpus:<file-stem>`` (the canonical citable slug).
    """
    text = (PAPERS_DIR / "README.md").read_text("utf-8")
    papers = []
    for line in text.splitlines():
        m = _TIER_A_ROW.match(line)
        if not m:
            continue
        stem, paper_cell, year, why = m.groups()
        if stem.lower() == "file":  # the header row
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
    """Tier B entries from the harvest index, metadata passed through
    verbatim (quality metrics per FR-LIT-8 F8.5 stay on the index file;
    the row keeps what the store models)."""
    if not CORPUS_INDEX.exists():
        log.warning("corpus-index.json not found at %s", CORPUS_INDEX)
        return []
    data = json.loads(CORPUS_INDEX.read_text("utf-8"))
    return [e for e in data.get("tierB", []) if e.get("ref")]


def _tier_a_body(paper: dict) -> str:
    """The searchable text for a seed: title + curator's why + local PDF
    text when a ``docs/papers/<stem>.pdf`` exists (PDFs are gitignored;
    absent ones degrade to metadata-only, never fail)."""
    parts = [paper["title"], paper["why"]]
    pdf_path = PAPERS_DIR / f"{paper['file']}.pdf"
    if pdf_path.exists():
        extracted = pdf.extract(pdf_path.read_bytes())
        if extracted["text"]:
            parts.append(extracted["text"])
    return "\n\n".join(parts)


def _upsert_corpus_paper(s: Session, values: dict) -> None:
    stmt = (
        sqlite_insert(Paper)
        .values(study_id=CORPUS_STUDY_ID, added_at="", **values)
        .on_conflict_do_update(
            index_elements=["study_id", "paper_ref"],
            set_={k: v for k, v in values.items() if k != "paper_ref"},
        )
    )
    s.execute(stmt)


def import_tier_a(s: Session) -> dict[str, int]:
    """Land the Tier A seeds; returns ref -> FTS chunk count."""
    indexed: dict[str, int] = {}
    for paper in parse_tier_a():
        _upsert_corpus_paper(
            s,
            {
                "paper_ref": paper["ref"],
                "title": paper["title"],
                "year": paper["year"],
                "abstract": paper["why"],
                "arxiv_id": paper["arxivId"],
                "doi": paper["doi"],
                "url": paper["url"],
                "item_type": "paper",
                "source": "docs/papers/README.md",
                "tier": "A",
            },
        )
        body = _tier_a_body(paper)
        indexed[paper["ref"]] = paper_index.index_paper(
            s, paper["ref"], paper["title"], body
        )
    return indexed


def import_tier_b(s: Session, *, batch_size: int = 500) -> dict[str, int]:
    """Land the harvested Tier B rows + FTS entries + via-edges."""
    seed_by_arxiv = {
        p["arxivId"]: p["ref"] for p in parse_tier_a() if p["arxivId"]
    }
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
            },
        )
        body = "\n\n".join(
            part for part in (entry.get("title", ""), entry.get("venue") or "")
            if part
        )
        indexed[ref] = paper_index.index_paper(
            s, ref, entry.get("title", ""), body
        )
        for via in entry.get("via", []):
            src = seed_by_arxiv.get(via)
            if not src:
                continue  # a seed the README no longer lists - skip, honest
            s.execute(
                sqlite_insert(PaperEdge)
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
        if (i + 1) % batch_size == 0:
            s.commit()
            log.info("Tier B: %d/%d landed", i + 1, len(entries))
    return indexed


def import_corpus(db_path: Path | str) -> dict:
    """One-shot, idempotent import of both tiers. Returns count summary."""
    factory = make_session_factory(db_path)
    with factory() as s:
        tier_a = import_tier_a(s)
        s.commit()
        tier_b = import_tier_b(s)
        s.commit()
    return {
        "tierA": {"count": len(tier_a), "chunks": sum(tier_a.values())},
        "tierB": {"count": len(tier_b), "chunks": sum(tier_b.values())},
    }


#: Seeds the F9.1 demo conversation must retrieve - the spot-check floor.
_DEMO_SEED_REFS = (
    "corpus:trust-in-ai-code-generation",
    "corpus:insecure-code-with-ai-assistants",
    "corpus:metr-early-2025-dev-productivity",
    "corpus:realhumaneval",
    "corpus:guidelines-empirical-llm-se",
)


def verify_import(db_path: Path | str) -> dict[str, bool]:
    """Spot-check an import against the source files (F8.1/F8.4): demo
    seeds present and searchable, row counts match the index, via-edges
    landed."""
    factory = make_session_factory(db_path)
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
            select(func.count()).select_from(Paper).where(
                Paper.study_id == CORPUS_STUDY_ID, Paper.tier == "A"
            )
        )
        count_b = s.scalar(
            select(func.count()).select_from(Paper).where(
                Paper.study_id == CORPUS_STUDY_ID, Paper.tier == "B"
            )
        )
        checks["tier-a-count-matches-readme"] = count_a == expected_a
        checks["tier-b-count-matches-index"] = count_b == expected_b
        checks["corpus-floor-1000"] = (count_a + count_b) >= 1000
        edge_count = s.scalar(
            select(func.count()).select_from(PaperEdge).where(
                PaperEdge.study_id == CORPUS_STUDY_ID,
                PaperEdge.kind == VIA_EDGE_KIND,
            )
        )
        checks["via-edges-landed"] = (edge_count or 0) > 0
        hits = paper_index.search(s, "over-trust AI generated code", limit=10)
        found = {h["paperRef"] for h in hits}
        checks["fts-finds-demo-seeds"] = bool(
            found & {_DEMO_SEED_REFS[0], _DEMO_SEED_REFS[1]}
        )
    return checks
