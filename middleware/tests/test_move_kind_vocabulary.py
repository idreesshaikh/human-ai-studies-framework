"""The frontend's move-kind vocabulary must equal the server's.

``design_llm._ALLOWED_KINDS`` is the server's whitelist: a move kind outside
it is dropped before ever reaching the wire (design_llm.py's own docstring:
"an unrecognized kind is dropped, never passed through blind"). The
frontend's ``MoveKind`` union in ``platform/src/lib/types.ts`` is supposed to
mirror it exactly, and ``KIND_LABEL: Record<DesignMove["kind"], string>`` in
MoveCard.tsx is typed to require an entry for every member.

They drifted. The union carried ``"set-threshold"`` - a kind the server has
never sent - and was missing three kinds the server does send:
``set-field`` and ``declare-task`` (the direct protocol-slot fills added this
session) and ``reconfigure-instrument`` (instrument tuning). Because the
union itself was wrong, TypeScript's exhaustiveness check on ``KIND_LABEL``
could not catch it - it verified completeness against the wrong set. A
design move of any of the three missing kinds rendered with no kind label at
all, silently, for as long as the two files disagreed.

This is a cheap, load-bearing thing to keep true — not something the current
Python + TypeScript workspace has any type-level way to enforce, so it is
kept true by name here.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TYPES_TS = REPO_ROOT / "platform" / "src" / "lib" / "types.ts"
MOVE_CARD_TSX = (
    REPO_ROOT / "platform" / "src" / "components" / "conversation" / "MoveCard.tsx"
)


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
    """Parse KIND_LABEL's own keys out of MoveCard.tsx — belt and braces
    alongside the TypeScript compiler's own exhaustiveness check, since a
    test failure here explains *why* in a way a red `npm run check` does
    not."""
    text = MOVE_CARD_TSX.read_text()
    start = text.index("const KIND_LABEL")
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
        f"MoveKind and KIND_LABEL disagree: "
        f"union-only={frontend - labeled}, label-only={labeled - frontend}"
    )
