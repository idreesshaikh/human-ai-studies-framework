"""Full-text index over ingested papers - the assistant's search corpus (FR-LIT-1/4)."""

from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from middleware import db

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
    """(Re)index one paper's text; returns the chunk count."""
    chunks = chunk_text(f"{title}\n\n{body}")
    if db.PG_FTS_AVAILABLE:
        return len(chunks)
    table = "paper_fts" if db.FTS5_AVAILABLE else "paper_chunks"
    s.execute(text(f"DELETE FROM {table} WHERE paper_ref = :ref"), {"ref": paper_ref})
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
    if db.PG_FTS_AVAILABLE:
        return
    table = "paper_fts" if db.FTS5_AVAILABLE else "paper_chunks"
    s.execute(text(f"DELETE FROM {table} WHERE paper_ref = :ref"), {"ref": paper_ref})


def _fts_query(query: str) -> str:
    """
    Sanitize a user query into an FTS5 MATCH expression: quote each term so punctuation
    can't inject FTS operators; OR them for recall.
    """
    terms = re.findall(r"[A-Za-z0-9]+", query)
    return " OR ".join(f'"{t}"' for t in terms)


def search(s: Session, query: str, *, limit: int = 6) -> list[dict]:
    """Top chunks matching ``query``: ``{paperRef, chunkIdx, snippet}``."""
    if not query.strip():
        return []
    if db.PG_FTS_AVAILABLE:
        rows = s.execute(
            text(
                "SELECT paper_ref, title, abstract FROM papers "
                "WHERE search_vector @@ plainto_tsquery('english', :q) "
                "ORDER BY ts_rank(search_vector, plainto_tsquery('english', :q)) DESC "
                "LIMIT :n"
            ),
            {"q": query, "n": limit},
        ).all()
        return [
            {
                "paperRef": ref,
                "chunkIdx": 0,
                "snippet": (abstract or title or "")[:240],
            }
            for ref, title, abstract in rows
        ]
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
        return [{"paperRef": r[0], "chunkIdx": r[1], "snippet": r[2]} for r in rows]
    terms = re.findall(r"[A-Za-z0-9][A-Za-z0-9-]{1,}", query.lower())
    rows = s.execute(text("SELECT paper_ref, chunk_idx, body FROM paper_chunks")).all()
    scored = []
    for ref, idx, body in rows:
        low = (body or "").lower()
        tokens = set(re.findall(r"[A-Za-z0-9][A-Za-z0-9-]{1,}", low))
        hits = sum(
            1
            for t in set(terms)
            if t in tokens or (t.endswith("s") and len(t) > 3 and t[:-1] in tokens)
        )
        if hits:
            scored.append((hits, ref, idx, body))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"paperRef": r, "chunkIdx": i, "snippet": b[:240]}
        for _, r, i, b in scored[:limit]
    ]
