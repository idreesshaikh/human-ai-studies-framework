"""Pseudonymization of mined actors (FR-CUR-1, F1.3)."""

from __future__ import annotations

import hashlib
import hmac
import secrets


def new_salt() -> str:
    """A fresh per-dataset salt."""
    return secrets.token_hex(32)


def pseudonym(salt: str, raw_actor: str, *, prefix: str = "actor") -> str:
    """Deterministic pseudonym for ``raw_actor`` under ``salt``."""
    normalized = raw_actor.strip().lower().encode("utf-8")
    digest = hmac.new(salt.encode("utf-8"), normalized, hashlib.sha256).hexdigest()
    return f"{prefix}-{digest[:16]}"
