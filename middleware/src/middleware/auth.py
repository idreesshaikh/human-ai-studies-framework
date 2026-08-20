"""Pluggable sign-in for the platform-facing endpoints (FR-OPS-5, D29)."""

from collections.abc import Callable
from dataclasses import dataclass, field

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


@dataclass
class ClerkVerifier:
    """Validates RS256 session JWTs against a JWKS endpoint."""

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
        except Exception as exc:
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
    """What the platform needs to render the right sign-in surface."""
    mode = resolve_mode(settings)
    doc: dict = {"mode": mode}
    if mode == "clerk" and settings.clerk_publishable_key:
        doc["clerkPublishableKey"] = settings.clerk_publishable_key
    return doc
