"""Pluggable sign-in for the platform-facing endpoints (FR-OPS-5, D29)."""

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import HTTPException

from middleware.settings import Settings

LOCAL_SUB = "local"


@dataclass(frozen=True)
class Identity:
    """The resolved caller identity."""

    sub: str
    display_name: str
    mode: str


# A verifier takes the raw ``Authorization`` header value, raises ``HTTPException`` when
# the request must not pass, and otherwise returns the resolved :class:`Identity`.
Verifier = Callable[[str], Identity]


def _local_identity(mode: str) -> Identity:
    return Identity(sub=LOCAL_SUB, display_name="You", mode=mode)


def _allow_all(_authorization: str) -> Identity:
    return _local_identity("none")


@dataclass(frozen=True)
class TokenVerifier:
    token: str

    def __call__(self, authorization: str) -> Identity:
        if authorization != f"Bearer {self.token}":
            raise HTTPException(401, "missing or invalid bearer token")
        return _local_identity("token")


def resolve_mode(settings: Settings) -> str:
    """The active auth mode: explicit ``MIDDLEWARE_AUTH``, else inferred."""
    mode = (settings.auth or "").strip().lower()
    if not mode:
        return "token" if settings.token else "none"
    if mode not in {"none", "token"}:
        raise ValueError(f"MIDDLEWARE_AUTH={mode!r}: expected none or token")
    return mode


def verifier_from_settings(settings: Settings) -> Verifier:
    mode = resolve_mode(settings)
    if mode == "none":
        return _allow_all
    if not settings.token:
        raise ValueError("MIDDLEWARE_AUTH=token requires MIDDLEWARE_TOKEN")
    return TokenVerifier(settings.token)


def public_config(settings: Settings) -> dict:
    """What the platform needs to render the right sign-in surface."""
    return {"mode": resolve_mode(settings)}
