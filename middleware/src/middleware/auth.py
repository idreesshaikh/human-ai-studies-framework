"""Pluggable sign-in for the dashboard-facing endpoints (FR-OPS-5, D29).

Three providers, one seam. The mode is ``MIDDLEWARE_AUTH`` or, when unset,
resolved from what is configured (zero-config self-hosting stays
zero-config):

- ``none``  - every request passes. The local/offline default (NFR-5).
- ``token`` - ``Authorization: Bearer <MIDDLEWARE_TOKEN>``. The default
  whenever ``MIDDLEWARE_TOKEN`` is set; unchanged behavior from MP-06.
- ``clerk`` - verify a Clerk-issued session JWT (RS256) against the
  instance's JWKS (``MIDDLEWARE_CLERK_JWKS_URL``). For hosted deployments
  that want a polished login; self-hosters never need it.

Ingest is never authenticated in any mode (NFR-1: sensors are
fire-and-forget). Misconfiguration fails loudly at startup, like the
stale-DB check - never quietly open.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from fastapi import HTTPException

from middleware.settings import Settings

#: A verifier takes the raw ``Authorization`` header value and raises
#: ``HTTPException`` when the request must not pass.
Verifier = Callable[[str], None]


def _allow_all(_authorization: str) -> None:
    return None


@dataclass(frozen=True)
class TokenVerifier:
    token: str

    def __call__(self, authorization: str) -> None:
        if authorization != f"Bearer {self.token}":
            raise HTTPException(401, "missing or invalid bearer token")


@dataclass
class ClerkVerifier:
    """Validates RS256 session JWTs against a JWKS endpoint.

    Key fetching/caching is delegated to ``jwt.PyJWKClient`` (pyjwt[crypto],
    D29 - never hand-roll signature verification). A JWKS outage fails
    closed with a 503, not open.
    """

    jwks_url: str
    issuer: str | None = None
    _jwk_client: object = field(default=None, repr=False)

    def _signing_key(self, token: str):
        import jwt

        if self._jwk_client is None:
            self._jwk_client = jwt.PyJWKClient(self.jwks_url)
        return self._jwk_client.get_signing_key_from_jwt(token).key

    def __call__(self, authorization: str) -> None:
        import jwt

        if not authorization.startswith("Bearer "):
            raise HTTPException(401, "missing bearer token")
        token = authorization.removeprefix("Bearer ")
        try:
            key = self._signing_key(token)
        except jwt.exceptions.PyJWTError as exc:
            raise HTTPException(401, f"invalid token: {exc}") from exc
        except Exception as exc:  # JWKS unreachable - fail closed, not open
            raise HTTPException(
                503, "sign-in temporarily unavailable (JWKS fetch failed)"
            ) from exc
        try:
            jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.issuer,
                options={"verify_aud": False},
            )
        except jwt.exceptions.PyJWTError as exc:
            raise HTTPException(401, f"invalid token: {exc}") from exc


def resolve_mode(settings: Settings) -> str:
    """The active auth mode: explicit ``MIDDLEWARE_AUTH``, else inferred."""
    mode = (settings.auth or "").strip().lower()
    if not mode:
        return "token" if settings.token else "none"
    if mode not in {"none", "token", "clerk"}:
        raise ValueError(
            f"MIDDLEWARE_AUTH={mode!r}: expected none, token, or clerk"
        )
    return mode


def verifier_from_settings(settings: Settings) -> Verifier:
    mode = resolve_mode(settings)
    if mode == "none":
        return _allow_all
    if mode == "token":
        if not settings.token:
            raise ValueError("MIDDLEWARE_AUTH=token requires MIDDLEWARE_TOKEN")
        return TokenVerifier(settings.token)
    if not settings.clerk_jwks_url:
        raise ValueError(
            "MIDDLEWARE_AUTH=clerk requires MIDDLEWARE_CLERK_JWKS_URL"
        )
    return ClerkVerifier(settings.clerk_jwks_url, settings.clerk_issuer)


def public_config(settings: Settings) -> dict:
    """What the dashboard needs to render the right sign-in surface.

    Never includes secrets: the Clerk *publishable* key is public by
    definition; the bearer token is obviously not exposed.
    """
    mode = resolve_mode(settings)
    doc: dict = {"mode": mode}
    if mode == "clerk" and settings.clerk_publishable_key:
        doc["clerkPublishableKey"] = settings.clerk_publishable_key
    return doc
