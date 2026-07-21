"""Pluggable sign-in for the platform-facing endpoints (FR-OPS-5, D29).

Three providers, one seam. The mode is ``MIDDLEWARE_AUTH`` or, when unset,
resolved from what is configured (zero-config self-hosting stays
zero-config):

- ``none``  - every request passes. The local/offline default (NFR-5).
- ``token`` - ``Authorization: Bearer <MIDDLEWARE_TOKEN>``. The default
  whenever ``MIDDLEWARE_TOKEN`` is set; unchanged behavior from.
- ``clerk`` - verify a Clerk-issued session JWT (RS256) against the
  instance's JWKS (``MIDDLEWARE_CLERK_JWKS_URL``). For hosted deployments
  that want a polished login; self-hosters never need it.

Ingest accepts an optional per-session credential (FR-ING-7): a valid one
server-stamps the join keys; an absent or invalid one still stores the row,
flagged - ingest never returns 401 and never drops (NFR-1). Misconfiguration
fails loudly at startup, like the stale-DB check - never quietly open.

 widened the seam: a verifier now returns an :class:`Identity` (the
JWT ``sub`` + display name + mode) instead of ``None``, so the project
choke point (:mod:`middleware.authz`) can resolve membership. Rejection
semantics are unchanged - verifiers still raise ``HTTPException`` on
``401``/``503``; only the success-path return type widened.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from fastapi import HTTPException

from middleware.settings import Settings

#: The synthetic identity sub for none/token modes - the single shared
#: facilitator (no second identity to distinguish). Matches the implicit
#: membership seeded at boot (db.IMPLICIT_IDENTITY_SUB).
LOCAL_SUB = "local"


@dataclass(frozen=True)
class Identity:
    """The resolved caller identity.

    - ``sub`` is the join key for membership lookup (``identity_sub``).
    - ``display_name`` surfaces in ``GET /me`` and the shell's account menu.
    - ``mode`` is the active auth mode (none/token/clerk) so the shell can
      unmount project UI in none/token (FR-PLAT-5).
    """

    sub: str
    display_name: str
    mode: str


#: A verifier takes the raw ``Authorization`` header value, raises
#: ``HTTPException`` when the request must not pass, and otherwise returns
#: the resolved :class:`Identity`.
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
        # Token mode is a single shared facilitator - there is no second
        # identity to distinguish, so every valid bearer resolves to the
        # local identity (the implicit project's owner).
        return _local_identity("token")


@dataclass
class ClerkVerifier:
    """Validates RS256 session JWTs against a JWKS endpoint.

    Key fetching/caching is delegated to ``jwt.PyJWKClient`` (pyjwt[crypto],
    D29 - never hand-roll signature verification). A JWKS outage fails
    closed with a 503, not open. On success the decoded claims (``sub``,
    ``name``/``email``) become an :class:`Identity` for membership lookup.
    """

    jwks_url: str
    issuer: str | None = None
    _jwk_client: object = field(default=None, repr=False)

    def _signing_key(self, token: str):
        import jwt

        if self._jwk_client is None:
            self._jwk_client = jwt.PyJWKClient(self.jwks_url)
        return self._jwk_client.get_signing_key_from_jwt(token).key

    def __call__(self, authorization: str) -> Identity:
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
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.issuer,
                options={"verify_aud": False},
            )
        except jwt.exceptions.PyJWTError as exc:
            raise HTTPException(401, f"invalid token: {exc}") from exc
        sub = str(claims.get("sub", ""))
        if not sub:
            raise HTTPException(401, "token carried no subject (sub)")
        name = (
            claims.get("name")
            or claims.get("email")
            or claims.get("preferred_username")
            or sub
        )
        return Identity(sub=sub, display_name=str(name), mode="clerk")


def resolve_mode(settings: Settings) -> str:
    """The active auth mode: explicit ``MIDDLEWARE_AUTH``, else inferred."""
    mode = (settings.auth or "").strip().lower()
    if not mode:
        return "token" if settings.token else "none"
    if mode not in {"none", "token", "clerk"}:
        raise ValueError(f"MIDDLEWARE_AUTH={mode!r}: expected none, token, or clerk")
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
        raise ValueError("MIDDLEWARE_AUTH=clerk requires MIDDLEWARE_CLERK_JWKS_URL")
    return ClerkVerifier(settings.clerk_jwks_url, settings.clerk_issuer)


def public_config(settings: Settings) -> dict:
    """What the platform needs to render the right sign-in surface.

    Never includes secrets: the Clerk *publishable* key is public by
    definition; the bearer token is obviously not exposed.
    """
    mode = resolve_mode(settings)
    doc: dict = {"mode": mode}
    if mode == "clerk" and settings.clerk_publishable_key:
        doc["clerkPublishableKey"] = settings.clerk_publishable_key
    return doc
