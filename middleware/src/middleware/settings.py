"""Environment-driven configuration.

Railway is the primary deployment target: PostgreSQL via DATABASE_URL (wired
to the Railway Postgres plugin as an explicit variable Reference — Railway
does NOT auto-inject a plugin's variables into another service) and Clerk
authentication. Local development uses the same PostgreSQL path via
docker-compose.yml — SQLite is a fallback for script-level testing only.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


def _sqlite_path(raw: str) -> Path:
    """``MIDDLEWARE_DB`` as a filesystem path.

    It is documented as a path, but ``sqlite:///data.sqlite3`` is the obvious
    thing to try and used to be accepted silently: the URL was pasted into
    another one (``sqlite:///sqlite:///data.sqlite3``), which is a valid
    *relative filename*, so the server started happily against an empty
    database that nobody had imported anything into. Nothing failed; the data
    was just somewhere else. Both spellings resolve to the same file now.
    """
    if raw.startswith("sqlite:"):
        rest = raw[len("sqlite:") :]
        # sqlite:////abs -> /abs ; sqlite:///rel -> rel
        stripped = rest.lstrip("/")
        return Path("/" + stripped if rest.startswith("////") else stripped)
    return Path(raw)


@dataclass(frozen=True)
class Settings:
    """Runtime configuration; every field has a ``MIDDLEWARE_*`` env var."""

    # --- database -------------------------------------------------------
    # Priority: DATABASE_URL (PostgreSQL, set by Railway or docker-compose)
    # > MIDDLEWARE_DB (SQLite path, local script testing only).
    # ``db_url`` is the resolved SQLAlchemy URL string used by
    # ``db.make_session_factory``; callers should use ``db_url``.

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
    # Priority: MIDDLEWARE_PORT (explicit operator override) > PORT (Railway
    # dynamically assigns this per-service and routes/healthchecks against
    # it — the app must actually bind here or every external probe reads
    # "service unavailable" even though the app is healthy internally) >
    # 8000 (the FR-ING-1 default every instrument leg's 127.0.0.1 endpoint
    # assumes for local/self-hosted use, where PORT is never set).
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
    # --- email delivery (member invitations, FR-PLAT-3) -----------------
    # Optional: when a Resend API key is set, invitations are emailed. Absent,
    # the platform degrades to the copy-link flow (no third-party required —
    # the invite still works, the researcher just shares the link themselves).
    resend_api_key: str | None = field(
        default_factory=lambda: os.environ.get("RESEND_API_KEY") or None
    )
    invite_from_email: str = field(
        default_factory=lambda: os.environ.get(
            "MIDDLEWARE_INVITE_FROM", "PHOENIX <onboarding@resend.dev>"
        )
    )
    # Absolute base for accept links in emails (e.g. https://app.example.com).
    # Falls back to the first CORS origin, then a relative link.
    public_base_url: str | None = field(
        default_factory=lambda: os.environ.get("MIDDLEWARE_PUBLIC_URL") or None
    )

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"
