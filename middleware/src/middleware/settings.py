"""Environment-driven configuration.

Everything defaults to a local, offline, single-laptop deployment (NFR-5,
NFR-7): SQLite file DB and an artifact directory under ``.study-data/``
(gitignored - participant data never enters git), port 8000 (FR-ING-1).
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Runtime configuration; every field has a ``MIDDLEWARE_*`` env var."""

    db_path: Path = field(
        default_factory=lambda: Path(
            os.environ.get("MIDDLEWARE_DB", ".study-data/middleware.sqlite3")
        )
    )
    data_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("MIDDLEWARE_DATA_DIR", ".study-data")
        )
    )
    #: Study protocol YAML; when set, ingest validates conditions/participants
    #: against it and flags mismatches (FR-ING-6). Unset = accept-all.
    protocol_path: Path | None = field(
        default_factory=lambda: (
            Path(p) if (p := os.environ.get("MIDDLEWARE_PROTOCOL")) else None
        )
    )
    port: int = field(
        default_factory=lambda: int(os.environ.get("MIDDLEWARE_PORT", "8000"))
    )
    #: Built web SPA to serve at ``/`` (NFR-7: one process serves the whole
    #: stack) — the React ``platform/`` app.
    #: Unset or missing directory = API-only.
    spa_dist: Path = field(
        default_factory=lambda: Path(os.environ.get("MIDDLEWARE_WEB", "platform/dist"))
    )
    #: Documents of record for the platform's plain-language tooltips
    #: (FR-DASH-9): the directory holding ``srs.md`` + ``glossary.md``.
    #: Missing = the endpoints return [] and the UI degrades to bare IDs.
    requirements_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("MIDDLEWARE_REQUIREMENTS_DIR", "requirements")
        )
    )
    #: Optional bearer token for the platform-facing query/task endpoints
    #:. Ingest stays open: sensors are fire-and-forget (NFR-1) and
    #: the deployment is local-first (NFR-5). Unset = no auth.
    token: str | None = field(
        default_factory=lambda: os.environ.get("MIDDLEWARE_TOKEN") or None
    )
    #: Sign-in provider (FR-OPS-5): ``none`` / ``token`` / ``clerk``.
    #: Unset = inferred (token when MIDDLEWARE_TOKEN is set, else none).
    auth: str | None = field(
        default_factory=lambda: os.environ.get("MIDDLEWARE_AUTH") or None
    )
    #: Clerk provider config (D29) - hosted deployments only.
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

    #: Origins allowed to call the API cross-origin (FR-OPS-6), comma-
    #: separated - e.g. a separately hosted platform preview during design
    #: iteration (D30). Unset = same-origin only (the default posture).
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip()
            for o in os.environ.get("MIDDLEWARE_CORS_ORIGINS", "").split(",")
            if o.strip()
        )
    )

    #: GitHub token for the curated-mining leg (FR-CUR-2), token-scoped.
    #: Runtime env only, never git/CI. Unset = the live source can't be
    #: reached; mining falls back to a configured cassette or reports the
    #: gap plainly (NFR-4 degrade-to-cache posture).
    github_token: str | None = field(
        default_factory=lambda: os.environ.get("MIDDLEWARE_GITHUB_TOKEN") or None
    )
    #: A recorded API cassette (``curated/.../cassettes/*.json``) to mine
    #: against instead of the live source. Set for the offline demo and CI so
    #: mining runs with zero tokens and zero network. When
    #: unset and a token exists, the live fetcher is used.
    mining_cassette: Path | None = field(
        default_factory=lambda: (
            Path(p) if (p := os.environ.get("MIDDLEWARE_MINING_CASSETTE")) else None
        )
    )

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"
