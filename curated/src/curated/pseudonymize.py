"""Pseudonymization of mined actors (FR-CUR-1, F1.3).

Privacy by construction extends to *strangers*: a mined author's identity
never enters the dataset in the clear. An actor's raw handle (a GitHub
login, a commit-author email) is mapped to ``participant_id`` through a
salted hash. The salt is per-dataset and lives only server-side; it is
never exported, so the pseudonyms cannot be re-identified from an exported
dataset even by someone who can enumerate logins.

This mirrors the extension's salted-hash discipline (FR-ETH-2) - the same
posture applied to public data, because public-data ethics are still
ethics.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets


def new_salt() -> str:
    """A fresh per-dataset salt. Generate once when the dataset is created;
    store it server-side (never in an export, never in git)."""
    return secrets.token_hex(32)


def pseudonym(salt: str, raw_actor: str, *, prefix: str = "actor") -> str:
    """Deterministic pseudonym for ``raw_actor`` under ``salt``.

    Deterministic under a fixed salt (so the same author across two PRs maps
    to the same ``participant_id`` - joins work), but unforgeable without the
    salt (HMAC-SHA256, not a bare hash, so it resists a login-enumeration
    dictionary attack). Case/whitespace-normalized so ``Alice`` and ``alice``
    are the same actor.
    """
    normalized = raw_actor.strip().lower().encode("utf-8")
    digest = hmac.new(salt.encode("utf-8"), normalized, hashlib.sha256).hexdigest()
    return f"{prefix}-{digest[:16]}"
