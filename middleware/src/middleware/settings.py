"""Environment-driven configuration."""

import os
from dataclasses import dataclass, field
from pathlib import Path


def _sqlite_path(raw: str) -> Path:
    """``MIDDLEWARE_DB`` as a filesystem path."""
    if raw.startswith("sqlite:"):
        rest = raw[len("sqlite:") :]
        stripped = rest.lstrip("/")
        return Path("/" + stripped if rest.startswith("////") else stripped)
    return Path(raw)


@dataclass(frozen=True)
class Settings:
    """Runtime configuration; every field has a ``MIDDLEWARE_*`` env var."""


    database_url: str | None = field(
        default_factory=lambda: os.environ.get("DATABASE_URL") or None
    )
    db_path: Path | None = field(
        default_factory=lambda: (
            None
            if os.environ.get("DATABASE_URL")
            else _sqlite_path(
                os.environ.get("MIDDLEWARE_DB", ".study-data/middleware.sqlite3")
            )
        )
    )

    @property
    def db_url(self) -> str:
        if self.database_url:
            url = self.database_url
            if url.startswith("postgres://"):
                url = "postgresql+psycopg://" + url[len("postgres://"):]
            elif url.startswith("postgresql://"):
                url = "postgresql+psycopg://" + url[len("postgresql://"):]
            return url
        return f"sqlite:///{self.db_path}"

    data_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("MIDDLEWARE_DATA_DIR", ".study-data")
        )
    )
    protocol_path: Path | None = field(
        default_factory=lambda: (
            Path(p) if (p := os.environ.get("MIDDLEWARE_PROTOCOL")) else None
        )
    )
    # Priority: MIDDLEWARE_PORT (explicit operator override) > PORT (Railway dynamically
    # assigns this per-service and routes/healthchecks against it — the app must
    # actually bind here or every external probe reads "service unavailable" even though
    # the app is healthy internally) > 8000 (the FR-ING-1 default every instrument leg's
    # 127.0.0.1 endpoint assumes for local/self-hosted use, where PORT is never set).
    port: int = field(
        default_factory=lambda: int(
            os.environ.get("MIDDLEWARE_PORT") or os.environ.get("PORT") or "8000"
        )
    )
    spa_dist: Path = field(
        default_factory=lambda: Path(os.environ.get("MIDDLEWARE_WEB", "platform/dist"))
    )
    token: str | None = field(
        default_factory=lambda: os.environ.get("MIDDLEWARE_TOKEN") or None
    )
    auth: str | None = field(
        default_factory=lambda: os.environ.get("MIDDLEWARE_AUTH") or None
    )
    clerk_jwks_url: str | None = field(
        default_factory=lambda: os.environ.get("MIDDLEWARE_CLERK_JWKS_URL") or None
    )
    clerk_issuer: str | None = field(
        default_factory=lambda: os.environ.get("MIDDLEWARE_CLERK_ISSUER") or None
    )
    clerk_publishable_key: str | None = field(
        default_factory=lambda: (
            os.environ.get("MIDDLEWARE_CLERK_PUBLISHABLE_KEY") or None
        )
    )
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip()
            for o in os.environ.get("MIDDLEWARE_CORS_ORIGINS", "").split(",")
            if o.strip()
        )
    )
    resend_api_key: str | None = field(
        default_factory=lambda: os.environ.get("RESEND_API_KEY") or None
    )
    invite_from_email: str = field(
        default_factory=lambda: os.environ.get(
            "MIDDLEWARE_INVITE_FROM", "PHOENIX <onboarding@resend.dev>"
        )
    )
    public_base_url: str | None = field(
        default_factory=lambda: os.environ.get("MIDDLEWARE_PUBLIC_URL") or None
    )

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"
