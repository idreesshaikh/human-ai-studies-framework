"""The frontend's move-kind vocabulary must equal the server's."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TYPES_TS = REPO_ROOT / "platform" / "src" / "lib" / "types.ts"
MOVE_CARD_TSX = (
    REPO_ROOT / "platform" / "src" / "components" / "conversation" / "MoveCard.tsx"
)
UI_TEXT_TS = REPO_ROOT / "platform" / "src" / "lib" / "uiText.ts"


def _server_kinds() -> set[str]:
    from middleware.design_llm import _ALLOWED_KINDS

    return set(_ALLOWED_KINDS)


def _frontend_move_kind_union() -> set[str]:
    """Parse the ``MoveKind`` union's string literals out of types.ts."""
    text = TYPES_TS.read_text()
    start = text.index("export type MoveKind =")
    end = text.index(";", start)
    block = text[start:end]
    return set(re.findall(r'"([a-z-]+)"', block))


def _kind_label_keys() -> set[str]:
    """
    The shared label map still covers every kind and MoveCard consumes it.
    """
    assert "moveEyebrow(move.kind, move.patch)" in MOVE_CARD_TSX.read_text()
    text = UI_TEXT_TS.read_text()
    start = text.index("const EYEBROW_BY_KIND")
    end = text.index("};", start)
    block = text[start:end]
    quoted = re.findall(r'"([a-z-]+)":', block)
    bare = re.findall(r"^\s*([a-z][a-zA-Z-]*):", block, re.MULTILINE)
    return set(quoted) | set(bare)


def test_frontend_move_kind_union_matches_the_server_whitelist():
    server = _server_kinds()
    frontend = _frontend_move_kind_union()
    missing = server - frontend
    extra = frontend - server
    assert not missing, f"server sends kinds the frontend union lacks: {missing}"
    assert not extra, f"frontend union claims kinds the server never sends: {extra}"


def test_move_card_labels_every_kind_the_union_declares():
    frontend = _frontend_move_kind_union()
    labeled = _kind_label_keys()
    assert frontend == labeled, (
        f"MoveKind and EYEBROW_BY_KIND disagree: "
        f"union-only={frontend - labeled}, label-only={labeled - frontend}"
    )
