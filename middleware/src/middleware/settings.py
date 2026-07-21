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
            else Path(os.environ.get("MIDDLEWARE_DB", ".study-data/middleware.sqlite3"))
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
    # The public-seeded-demo posture (start_with_seed.sh reseeds on every
    # boot when this is "1"): only in this mode is the boot protocol's study
    # the intentional *shared public demo* (FR-PLAT-4) — never true by
    # default for a self-hosted researcher's real study, which must never
    # get silently exposed as the public demo project.
    seed_on_start: bool = field(
        default_factory=lambda: os.environ.get("MIDDLEWARE_SEED_ON_START") == "1"
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
    requirements_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("MIDDLEWARE_REQUIREMENTS_DIR", "requirements")
        )
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
    github_token: str | None = field(
        default_factory=lambda: os.environ.get("MIDDLEWARE_GITHUB_TOKEN") or None
    )
    mining_cassette: Path | None = field(
        default_factory=lambda: (
            Path(p) if (p := os.environ.get("MIDDLEWARE_MINING_CASSETTE")) else None
        )
    )

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"
