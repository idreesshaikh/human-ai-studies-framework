"""Full-text index over ingested papers - the assistant's search corpus
(FR-LIT-1/4).

SQLite's built-in **FTS5** is enough at this scale (a study cites dozens of
papers, not millions) - no vector DB, no embedding service, nothing to run
(a build decision, recorded in `requirements/build-vs-adopt.md` D21). Text
is chunked so a citation can point at a section (``[paper-ref §chunk]``).
When the SQLite build lacks FTS5 the same API falls back to a LIKE scan over
a plain table, so the assistant still answers offline on a minimal SQLite.
"""

from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from middleware import db

#: Chunk size in characters - large enough to hold a section's gist, small
#: enough that a citation localizes the claim.
CHUNK_CHARS = 1200


def chunk_text(body: str, *, size: int = CHUNK_CHARS) -> list[str]:
    """Split on blank lines, packing paragraphs up to ``size`` chars."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", body or "") if p.strip()]
    chunks: list[str] = []
    buf = ""
    for para in paras:
        if buf and len(buf) + len(para) > size:
            chunks.append(buf)
            buf = para
        else:
            buf = f"{buf}\n\n{para}" if buf else para
    if buf:
        chunks.append(buf)
    return chunks


def index_paper(s: Session, paper_ref: str, title: str, body: str) -> int:
    """(Re)index one paper's text; returns the chunk count. The title +
    abstract lead so a metadata-only paper (no PDF) is still searchable."""
    table = "paper_fts" if db.FTS5_AVAILABLE else "paper_chunks"
    s.execute(
        text(f"DELETE FROM {table} WHERE paper_ref = :ref"), {"ref": paper_ref}
    )
    chunks = chunk_text(f"{title}\n\n{body}")
    for i, chunk in enumerate(chunks):
        s.execute(
            text(
                f"INSERT INTO {table} (paper_ref, chunk_idx, body) "
                "VALUES (:ref, :i, :b)"
            ),
            {"ref": paper_ref, "i": i, "b": chunk},
        )
    return len(chunks)


def deindex_paper(s: Session, paper_ref: str) -> None:
    table = "paper_fts" if db.FTS5_AVAILABLE else "paper_chunks"
    s.execute(
        text(f"DELETE FROM {table} WHERE paper_ref = :ref"), {"ref": paper_ref}
    )


def _fts_query(query: str) -> str:
    """Sanitize a user query into an FTS5 MATCH expression: quote each term so
    punctuation can't inject FTS operators; OR them for recall."""
    terms = re.findall(r"[A-Za-z0-9]+", query)
    return " OR ".join(f'"{t}"' for t in terms)


def search(s: Session, query: str, *, limit: int = 6) -> list[dict]:
    """Top chunks matching ``query``: ``{paperRef, chunkIdx, snippet}``.

    The assistant's ``search_papers`` tool (FR-LIT-4). Returns paper *text*
    only - never a participant event, by construction (FR-ETH-4)."""
    if not query.strip():
        return []
    if db.FTS5_AVAILABLE:
        match = _fts_query(query)
        if not match:
            return []
        rows = s.execute(
            text(
                "SELECT paper_ref, chunk_idx, "
                "snippet(paper_fts, 2, '[', ']', ' … ', 18) AS snip "
                "FROM paper_fts WHERE paper_fts MATCH :q "
                "ORDER BY bm25(paper_fts) LIMIT :n"
            ),
            {"q": match, "n": limit},
        ).all()
        return [
            {"paperRef": r[0], "chunkIdx": r[1], "snippet": r[2]} for r in rows
        ]
    # LIKE fallback: rank by number of distinct terms present.
    terms = re.findall(r"[A-Za-z0-9]+", query.lower())
    rows = s.execute(text("SELECT paper_ref, chunk_idx, body FROM paper_chunks")).all()
    scored = []
    for ref, idx, body in rows:
        low = (body or "").lower()
        hits = sum(1 for t in set(terms) if t in low)
        if hits:
            scored.append((hits, ref, idx, body))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"paperRef": r, "chunkIdx": i, "snippet": b[:240]}
        for _, r, i, b in scored[:limit]
    ]
