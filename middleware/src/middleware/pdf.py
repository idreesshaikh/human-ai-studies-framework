"""PDF text + title extraction for paper ingest (FR-LIT-1; decision D21).

PyMuPDF (``fitz``) extracts text locally - the bytes never leave the machine
(NFR-5). The metadata of record still comes from Semantic Scholar (D8); this
is only the *full text* for the assistant's search and a *title guess* to
enrich by when the PDF carries no DOI. A scanned or unreadable PDF degrades
to empty text rather than failing the ingest.
"""

from __future__ import annotations


def extract(content: bytes) -> dict:
    """Return ``{title, text}`` from PDF bytes. Best-effort: any parse error
    yields empties so ingest can fall back to metadata-only."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return {"title": "", "text": ""}
    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except Exception:  # noqa: BLE001 - corrupt/non-PDF bytes
        return {"title": "", "text": ""}
    try:
        pages = [page.get_text() for page in doc]
        title = str(doc.metadata.get("title") or "").strip()
    finally:
        doc.close()
    text = "\n\n".join(pages).strip()
    if not title:
        title = _title_guess(text)
    return {"title": title, "text": text}


def _title_guess(text: str) -> str:
    """First substantial line as a title guess (metadata-free PDFs)."""
    for line in text.splitlines():
        line = line.strip()
        if len(line) >= 12 and not line.isdigit():
            return line[:300]
    return ""
