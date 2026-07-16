"""Serve the requirements of record to the dashboard (FR-DASH-9).

The dashboard explains every requirement ID and domain term it shows with a
plain-language tooltip. That text is parsed **live from the documents of
record** - ``requirements/srs.md`` and ``requirements/glossary.md`` - so the
UI can never drift from the SRS (the alternative, a hand-copied map in the
frontend, had already drifted to 13 of 71 requirements when this landed).

Deliberately tolerant, line-oriented GFM-table parsing - no markdown
dependency. Missing files degrade to empty lists (the dashboard falls back
to its built-in map, then to bare IDs), matching the offline posture of
every other view (NFR-7).
"""

from __future__ import annotations

import re
from pathlib import Path

#: Requirement IDs as they appear in the SRS tables (a superseded row wraps
#: the ID in ``~~``, which is stripped before matching).
_ID = re.compile(r"^(?:FR|NFR)-[A-Z]*-?\d+$")
#: Split on pipes that are not escaped as ``\|`` (used inside definitions).
_PIPE = re.compile(r"(?<!\\)\|")
#: A bolded glossary term, optionally followed by a qualifier: ``**Paper**
#: *(artifact)*`` -> ``Paper``.
_TERM = re.compile(r"\*\*(.+?)\*\*")


def _cells(line: str) -> list[str]:
    """The stripped cell texts of one table row (without the edge pipes)."""
    parts = _PIPE.split(line)
    return [p.strip().replace("\\|", "|") for p in parts[1:-1]]


def _plain(text: str) -> str:
    """Strip the markdown emphasis the SRS uses (bold, strikethrough)."""
    return text.replace("**", "").replace("~~", "").strip()


def parse_srs(path: Path) -> list[dict]:
    """Every requirement row of the SRS as ``{id, priority, text, status}``.

    FR tables have five columns (ID | P | Requirement | Rationale | Status);
    the NFR table has four (no Status) - its ``status`` is ``""``. Superseded
    rows (``~~FR-…~~``) are included, de-struck, so their IDs still resolve.
    """
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text().splitlines():
        if not line.startswith("|"):
            continue
        cells = _cells(line)
        if len(cells) < 4:
            continue
        rid = _plain(cells[0])
        if not _ID.match(rid):
            continue  # header / separator / prose rows
        rows.append(
            {
                "id": rid,
                "priority": _plain(cells[1]),
                "text": _plain(cells[2]),
                "status": _plain(cells[4]) if len(cells) > 4 else "",
            }
        )
    return rows


def parse_glossary(path: Path) -> list[dict]:
    """Every glossary row as ``{term, definition}``. Terms are the bolded
    names (qualifiers like ``*(artifact)*`` are not part of the key)."""
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text().splitlines():
        if not line.startswith("|"):
            continue
        cells = _cells(line)
        if len(cells) < 2:
            continue
        m = _TERM.search(cells[0])
        if not m:
            continue  # header / separator rows
        rows.append({"term": m.group(1).strip(), "definition": _plain(cells[1])})
    return rows
