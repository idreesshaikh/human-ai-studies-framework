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
    #: Built dashboard SPA to serve at ``/`` (NFR-7: one process serves the
    #: whole stack). Unset or missing directory = API-only.
    dashboard_dist: Path = field(
        default_factory=lambda: Path(
            os.environ.get("MIDDLEWARE_DASHBOARD", "dashboard/dist")
        )
    )
    #: Documents of record for the dashboard's plain-language tooltips
    #: (FR-DASH-9): the directory holding ``srs.md`` + ``glossary.md``.
    #: Missing = the endpoints return [] and the UI degrades to bare IDs.
    requirements_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("MIDDLEWARE_REQUIREMENTS_DIR", "requirements")
        )
    )
    #: Optional bearer token for the dashboard-facing query/task endpoints
    #: (MP-06). Ingest stays open: sensors are fire-and-forget (NFR-1) and
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
        default_factory=lambda: os.environ.get("MIDDLEWARE_CLERK_JWKS_URL")
        or None
    )
    clerk_issuer: str | None = field(
        default_factory=lambda: os.environ.get("MIDDLEWARE_CLERK_ISSUER")
        or None
    )
    clerk_publishable_key: str | None = field(
        default_factory=lambda: os.environ.get(
            "MIDDLEWARE_CLERK_PUBLISHABLE_KEY"
        )
        or None
    )

    #: Zotero import (FR-LIT-5, D9): the desktop app's local API, plus the
    #: web-API fallback credentials. Unset credentials = local-only.
    zotero_local_url: str = field(
        default_factory=lambda: os.environ.get(
            "MIDDLEWARE_ZOTERO_LOCAL_URL", "http://127.0.0.1:23119"
        )
    )
    zotero_user_id: str | None = field(
        default_factory=lambda: os.environ.get("MIDDLEWARE_ZOTERO_USER_ID") or None
    )
    zotero_api_key: str | None = field(
        default_factory=lambda: os.environ.get("MIDDLEWARE_ZOTERO_API_KEY") or None
    )

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"
