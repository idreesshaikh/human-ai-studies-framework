"""SQLAlchemy models and engine setup.

Supports both SQLite (local dev / legacy) and PostgreSQL (Railway production).
The active backend is determined by ``Settings.db_url``:

- ``sqlite:///...``          → SQLite, single file, local-first
- ``postgresql+psycopg://...`` → PostgreSQL, managed by Railway

Idempotency contracts are preserved on both backends:

- ``events`` UNIQUE on ``(session_id, source, seq)``       → ``upsert_do_nothing``
- ``metric_rows`` UNIQUE on ``row_hash``                    → ``upsert_do_nothing``
- ``papers`` UNIQUE on ``(study_id, paper_ref)``            → ``upsert_do_update``
- ``paper_edges`` UNIQUE on ``(study_id, src, dst, kind)``  → ``upsert_do_nothing``
- ``paper_links`` UNIQUE on ``(study_id, paper_ref, target)`` → ``upsert_do_nothing``
- ``aggregate_shapes`` UNIQUE on ``(metric, key)``          → ``upsert_do_nothing``

All callers use the ``upsert_do_nothing`` / ``upsert_do_update`` helpers
exported from this module; they pick the right dialect automatically.

Full-text search:
- SQLite: FTS5 virtual table (``paper_fts``) when available, else ``paper_chunks``
- PostgreSQL: ``tsvector`` column on ``papers`` table; falls back to ``LIKE``
  scan when the column is absent (same degraded-mode contract as SQLite).
"""

import json
import logging
import time
from hashlib import sha256
from pathlib import Path

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

log = logging.getLogger("middleware.db")

# ---------------------------------------------------------------------------
# Well-known constants (unchanged)
# ---------------------------------------------------------------------------

IMPLICIT_PROJECT_SLUG = "implicit"
IMPLICIT_PROJECT_ID = "implicit"
IMPLICIT_IDENTITY_SUB = "local"
DEMO_PROJECT_SLUG = "demo"
CORPUS_STUDY_ID = "platform-corpus"
ROLES = ("owner", "researcher", "viewer")


# ---------------------------------------------------------------------------
# ORM base + models  (schema unchanged from original)
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class Event(Base):
    """One StudyEvent row (extension schema v2)."""

    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("session_id", "source", "seq", name="uq_session_source_seq"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, index=True)
    source: Mapped[str] = mapped_column(String, index=True, default="cognitive-overlay")
    seq: Mapped[int] = mapped_column(Integer)
    participant_id: Mapped[str] = mapped_column(String, index=True)
    condition: Mapped[str] = mapped_column(String)
    v: Mapped[int] = mapped_column(Integer)
    ts: Mapped[str] = mapped_column(String, index=True)
    mono: Mapped[float] = mapped_column()
    type: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    flags: Mapped[list] = mapped_column(JSON, default=list)
    received_at: Mapped[str] = mapped_column(String)


class MetricRow(Base):
    """One static-metrics row (function- or file-level), as ingested JSONL."""

    __tablename__ = "metric_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table: Mapped[str] = mapped_column(String)
    session_id: Mapped[str] = mapped_column(String, index=True)
    participant_id: Mapped[str] = mapped_column(String, index=True)
    condition: Mapped[str] = mapped_column(String)
    timestamp: Mapped[str] = mapped_column(String, index=True)
    schema_version: Mapped[int] = mapped_column(Integer)
    row: Mapped[dict] = mapped_column(JSON)
    row_hash: Mapped[str] = mapped_column(String, unique=True)
    flags: Mapped[list] = mapped_column(JSON, default=list)
    received_at: Mapped[str] = mapped_column(String)

    @staticmethod
    def hash_row(table: str, row: dict) -> str:
        canonical = json.dumps(row, sort_keys=True, separators=(",", ":"))
        return sha256(f"{table}\n{canonical}".encode()).hexdigest()


class StoredFile(Base):
    """An uploaded artifact indexed here (FR-ING-5)."""

    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("filename", "sha256", name="uq_filename_sha256"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String)
    stored_path: Mapped[str] = mapped_column(String)
    content_type: Mapped[str] = mapped_column(String, default="")
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String, index=True)
    session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    participant_id: Mapped[str | None] = mapped_column(String, nullable=True)
    uploaded_at: Mapped[str] = mapped_column(String)


class Paper(Base):
    """One paper in a study's paper set (FR-LIT-1)."""

    __tablename__ = "papers"
    __table_args__ = (
        UniqueConstraint("study_id", "paper_ref", name="uq_study_paper_ref"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    paper_ref: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String, default="")
    authors: Mapped[list] = mapped_column(JSON, default=list)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    venue: Mapped[str] = mapped_column(String, default="")
    abstract: Mapped[str] = mapped_column(Text, default="")
    doi: Mapped[str] = mapped_column(String, default="")
    arxiv_id: Mapped[str] = mapped_column(String, default="")
    url: Mapped[str] = mapped_column(String, default="")
    item_type: Mapped[str] = mapped_column(String, default="")
    source: Mapped[str] = mapped_column(String, default="id")
    zotero_key: Mapped[str] = mapped_column(String, default="")
    s2_id: Mapped[str] = mapped_column(String, default="")
    citation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    full_text: Mapped[str] = mapped_column(Text, default="")
    tier: Mapped[str] = mapped_column(String, default="study", index=True)
    added_via: Mapped[str] = mapped_column(String, default="")
    match_reason: Mapped[str] = mapped_column(Text, default="")
    added_at: Mapped[str] = mapped_column(String)


class PaperEdge(Base):
    """One citation-graph edge (FR-LIT-2)."""

    __tablename__ = "paper_edges"
    __table_args__ = (
        UniqueConstraint(
            "study_id", "src_ref", "dst_ref", "kind", name="uq_paper_edge"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    src_ref: Mapped[str] = mapped_column(String, index=True)
    dst_ref: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String)
    dst_title: Mapped[str] = mapped_column(String, default="")
    dst_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dst_citation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PaperLink(Base):
    """A paper ↔ protocol-element link (FR-LIT-3)."""

    __tablename__ = "paper_links"
    __table_args__ = (
        UniqueConstraint("study_id", "paper_ref", "target", name="uq_paper_link"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    paper_ref: Mapped[str] = mapped_column(String, index=True)
    target: Mapped[str] = mapped_column(String)


class S2Cache(Base):
    """Cached Semantic Scholar responses (D8, NFR-7)."""

    __tablename__ = "s2_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String, unique=True)
    body: Mapped[dict] = mapped_column(JSON)
    fetched_at: Mapped[str] = mapped_column(String)


class Finding(Base):
    """Operational-findings log (FR-META-1)."""

    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String, default="", index=True)
    requirement_id: Mapped[str] = mapped_column(String, default="")
    message: Mapped[str] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String, default="open")


class RecipeRun(Base):
    """One recorded analysis-recipe run."""

    __tablename__ = "recipe_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    recipe_id: Mapped[str] = mapped_column(String, index=True)
    answers: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String, default="ok")
    note: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[str] = mapped_column(String)


class TaskCard(Base):
    """Manual task-board card."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="open")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(String)


class Project(Base):
    """One research project — the scoping root (FR-PLAT-1)."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    slug: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_by: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[str] = mapped_column(String)


class Membership(Base):
    """One identity's role on one project (FR-PLAT-2)."""

    __tablename__ = "memberships"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'researcher', 'viewer')",
            name="ck_membership_role",
        ),
    )

    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id"), primary_key=True
    )
    identity_sub: Mapped[str] = mapped_column(String, primary_key=True)
    role: Mapped[str] = mapped_column(String)
    invited_by: Mapped[str] = mapped_column(String, default="")
    joined_at: Mapped[str] = mapped_column(String)


class Invitation(Base):
    """A pending email-link invitation (FR-PLAT-3)."""

    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id"), index=True
    )
    email: Mapped[str] = mapped_column(String, default="")
    role: Mapped[str] = mapped_column(String)
    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    expires_at: Mapped[str] = mapped_column(String)
    accepted_at: Mapped[str | None] = mapped_column(String, nullable=True)


class EnrollmentToken(Base):
    """A pairing token binding a study + participant + condition (FR-INST-20).

    ``grain`` is 'participant' (reusable across that participant's sessions)
    or 'session' (single-use). ``token`` is what the participant pastes (inside
    a connection string); ``credential`` is the short-lived bearer minted on
    redeem and sent on ingest so the middleware can server-stamp join keys
    (FR-ING-7). Mirrors the ``Invitation`` mint/expire/revoke shape.
    """

    __tablename__ = "enrollment_tokens"
    __table_args__ = (
        CheckConstraint(
            "grain IN ('participant', 'session')", name="ck_enrollment_grain"
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    study_id: Mapped[str] = mapped_column(
        String, ForeignKey("studies.id"), index=True
    )
    participant_id: Mapped[str] = mapped_column(String)
    condition: Mapped[str] = mapped_column(String)
    grain: Mapped[str] = mapped_column(String)
    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    #: Minted on redeem; sent as the ingest bearer. NULL until first redeem.
    credential: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    expires_at: Mapped[str] = mapped_column(String)
    revoked_at: Mapped[str | None] = mapped_column(String, nullable=True)
    redeemed_at: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[str] = mapped_column(String)


class Study(Base):
    """A reified study row (FR-PLAT-1)."""

    __tablename__ = "studies"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id"), index=True
    )
    protocol_version: Mapped[str] = mapped_column(String, default="")
    phase: Mapped[str] = mapped_column(String, default="")
    data_path: Mapped[str] = mapped_column(String, default="")


class MiningJob(Base):
    """A curated-dataset mining job (FR-CUR-2)."""

    __tablename__ = "mining_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    source: Mapped[str] = mapped_column(String, default="github")
    state: Mapped[str] = mapped_column(String, default="declared", index=True)
    cursor: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    coverage: Mapped[dict] = mapped_column(JSON, default=dict)
    fired_heuristics: Mapped[list] = mapped_column(JSON, default=list)
    salt: Mapped[str] = mapped_column(String, default="")
    status_message: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[str] = mapped_column(String, default="")
    updated_at: Mapped[str] = mapped_column(String, default="")


class CuratedDataset(Base):
    """A curated dataset + its validity-threats record (FR-CUR-3)."""

    __tablename__ = "curated_datasets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    job_id: Mapped[str] = mapped_column(String, index=True)
    threats_record: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    event_counts: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String, default="")


class ConversationTurn(Base):
    """One turn of a study's design conversation (FR-CONV-1)."""

    __tablename__ = "conversation_turns"
    __table_args__ = (
        UniqueConstraint("study_id", "seq", name="uq_conversation_turn_seq"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    seq: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String)
    author: Mapped[str] = mapped_column(String, default="")
    text: Mapped[str] = mapped_column(Text, default="")
    retrieved_refs: Mapped[list] = mapped_column(JSON, default=list)
    redacted: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String)
    #: "llm" | "scripted" - which path produced this platform turn
    #: (FR-CONV-1.4), so the elicitation record (FR-CONV-6) honestly
    #: records how each claim was produced. Empty for researcher turns.
    source: Mapped[str] = mapped_column(String, default="")


class DesignMoveRow(Base):
    """One platform-proposed protocol change (FR-CONV-1.2)."""

    __tablename__ = "design_moves"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    turn_id: Mapped[str] = mapped_column(
        String, ForeignKey("conversation_turns.id"), index=True
    )
    kind: Mapped[str] = mapped_column(String)
    target: Mapped[str] = mapped_column(String, default="")
    proposal: Mapped[str] = mapped_column(Text, default="")
    patch: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    grounding: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String, default="proposed")
    decided_by: Mapped[str] = mapped_column(String, default="")
    decided_at: Mapped[str] = mapped_column(String, default="")


class Compilation(Base):
    """One deterministic compile of accepted moves (FR-CONV-3)."""

    __tablename__ = "compilations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    base_sha256: Mapped[str] = mapped_column(String, default="")
    draft_yaml: Mapped[str] = mapped_column(Text, default="")
    diff: Mapped[str] = mapped_column(Text, default="")
    hunk_trace: Mapped[list] = mapped_column(JSON, default=list)
    move_ids: Mapped[list] = mapped_column(JSON, default=list)
    errors: Mapped[list] = mapped_column(JSON, default=list)
    unresolved: Mapped[list] = mapped_column(JSON, default=list)
    valid: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String)
    applied_at: Mapped[str] = mapped_column(String, default="")


class ApprovalEvent(Base):
    """Audit row for every applied diff (FR-CONV-3.3)."""

    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    compilation_id: Mapped[str] = mapped_column(
        String, ForeignKey("compilations.id"), index=True
    )
    approved_by: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    at: Mapped[str] = mapped_column(String)


class ProtocolDraftRow(Base):
    """The study's current compiled draft — one row per study."""

    __tablename__ = "protocol_drafts"

    study_id: Mapped[str] = mapped_column(String, primary_key=True)
    yaml: Mapped[str] = mapped_column(Text, default="")
    compilation_id: Mapped[str] = mapped_column(String, default="")
    updated_at: Mapped[str] = mapped_column(String, default="")


class StudyEvolution(Base):
    """One row per study tracking its amendment lifecycle (FR-CONV-4)."""

    __tablename__ = "study_evolution"

    study_id: Mapped[str] = mapped_column(String, primary_key=True)
    ethics_approved_at: Mapped[str] = mapped_column(String, default="")
    approved_yaml: Mapped[str] = mapped_column(Text, default="")
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    pending_reapproval: Mapped[str] = mapped_column(String, default="")
    updated_at: Mapped[str] = mapped_column(String, default="")


class Amendment(Base):
    """One post-ethics protocol change (FR-CONV-4.2)."""

    __tablename__ = "amendments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    compilation_id: Mapped[str] = mapped_column(String, default="")
    from_version: Mapped[int] = mapped_column(Integer)
    to_version: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(Text, default="")
    changes: Mapped[list] = mapped_column(JSON, default=list)
    rationale: Mapped[str] = mapped_column(Text, default="")
    grounding: Mapped[list] = mapped_column(JSON, default=list)
    consent_relevant: Mapped[int] = mapped_column(Integer, default=0)
    consent_reasons: Mapped[list] = mapped_column(JSON, default=list)
    approved_by: Mapped[str] = mapped_column(String, default="")
    role: Mapped[str] = mapped_column(String, default="")
    reapproval_artifact: Mapped[str] = mapped_column(String, default="")
    reapproved_at: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[str] = mapped_column(String)


class SessionOpen(Base):
    """The protocol version a data-collection session opened under (FR-CONV-4.4)."""

    __tablename__ = "session_opens"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    protocol_version: Mapped[int] = mapped_column(Integer)
    opened_at: Mapped[str] = mapped_column(String)


class UserProfile(Base):
    """A signed-in identity's per-user preferences (FR-OPS-7, D29).

    Keyed by ``identity_sub`` (the Clerk ``sub`` in clerk mode, ``local`` in
    none/token mode) so a hosted, multi-tenant deployment can persist a
    profile per person — theme, default assistant model, saved views — that
    follows them across devices. The prefs blob is schema-less by design; the
    server stores whatever the client sends within ``KNOWN_PREF_KEYS`` and
    the UI owns the per-key semantics. A missing row reads as empty prefs.
    """

    __tablename__ = "user_profiles"

    identity_sub: Mapped[str] = mapped_column(String, primary_key=True)
    prefs: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[str] = mapped_column(String, default="")


class TemplateSubmission(Base):
    """Third-party template contributed for registry review (FR-TPL-5).

    A submitter provides a YAML template; owners of the implicit project
    (single-facilitator) or any project (multi-tenant) can approve (which
    writes it to the registry) or reject it.
    """

    __tablename__ = "template_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submitter_sub: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    template_yaml: Mapped[str] = mapped_column(Text)
    # status: pending | approved | rejected
    status: Mapped[str] = mapped_column(String, default="pending")
    reviewer_sub: Mapped[str] = mapped_column(String, default="")
    review_comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(String)
    reviewed_at: Mapped[str] = mapped_column(String, default="")


class AggregateShape(Base):
    """One anonymous cross-project usage shape (FR-CONV-5.3)."""

    __tablename__ = "aggregate_shapes"
    __table_args__ = (UniqueConstraint("metric", "key", name="uq_aggregate_shape"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metric: Mapped[str] = mapped_column(String, index=True)
    key: Mapped[str] = mapped_column(String)
    count: Mapped[int] = mapped_column(Integer, default=0)
    computed_at: Mapped[str] = mapped_column(String, default="")


# ---------------------------------------------------------------------------
# Dialect-aware upsert helpers
# ---------------------------------------------------------------------------
# These are the *only* place in the codebase that touches dialect-specific
# insert syntax.  app.py imports and calls them; it never imports
# ``sqlite_insert`` directly any more.

def _is_postgres(engine) -> bool:
    return engine.dialect.name == "postgresql"


def upsert_do_nothing(engine, model, rows: list[dict]) -> int:
    """INSERT … ON CONFLICT DO NOTHING for the given model rows.

    Returns the number of rows actually inserted (0 on full duplicate batch).
    Works on both SQLite and PostgreSQL.
    """
    if not rows:
        return 0
    from sqlalchemy.orm import Session as _Session

    with _Session(engine) as s:
        if _is_postgres(engine):
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            stmt = pg_insert(model).values(rows).on_conflict_do_nothing()
        else:
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert
            stmt = sqlite_insert(model).values(rows).on_conflict_do_nothing()
        pk = model.__mapper__.primary_key[0]
        inserted = len(s.execute(stmt.returning(pk)).fetchall())
        s.commit()
        return inserted


def upsert_do_update(
    engine,
    model,
    rows: list[dict],
    conflict_cols: list[str],
    update_cols: dict,
) -> None:
    """INSERT … ON CONFLICT (conflict_cols) DO UPDATE SET update_cols.

    Works on both SQLite and PostgreSQL.  ``update_cols`` maps column name →
    value expression (plain value or SQLAlchemy expression).
    """
    if not rows:
        return
    from sqlalchemy.orm import Session as _Session

    with _Session(engine) as s:
        if _is_postgres(engine):
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            stmt = (
                pg_insert(model)
                .values(rows)
                .on_conflict_do_update(index_elements=conflict_cols, set_=update_cols)
            )
        else:
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert
            stmt = (
                sqlite_insert(model)
                .values(rows)
                .on_conflict_do_update(index_elements=conflict_cols, set_=update_cols)
            )
        s.execute(stmt)
        s.commit()


# ---------------------------------------------------------------------------
# Engine / session factory
# ---------------------------------------------------------------------------

#: Set by ``make_session_factory``; used by ``paper_index`` and the
#: corpus importer to decide which FTS path to take.
FTS5_AVAILABLE: bool = False
PG_FTS_AVAILABLE: bool = False

#: The shared engine; exposed so ``paper_index`` and the corpus importer
#: can build dialect-aware statements without needing to re-parse the URL.
_engine = None


def get_engine():
    """Return the shared engine (set by ``make_session_factory``)."""
    return _engine


def make_session_factory(db_url: str | Path) -> sessionmaker:
    """Create the schema if needed and return a session factory.

    ``db_url`` is a fully-qualified SQLAlchemy URL string, e.g.:
    - ``sqlite:///path/to/file.sqlite3``
    - ``postgresql+psycopg://user:pass@host/db``

    A bare :class:`~pathlib.Path` (or a ``sqlite:///``-less path string) is
    accepted and treated as a SQLite file path — convenient for tests and
    scripts that already hold a ``Path``. For PostgreSQL a connection pool
    appropriate for a managed database is configured (pool_size=5,
    connect_timeout=30 s).
    """
    global _engine, FTS5_AVAILABLE, PG_FTS_AVAILABLE

    # Accept a Path (or a bare path string) as a SQLite file location.
    if isinstance(db_url, Path):
        db_url = f"sqlite:///{db_url}"
    elif isinstance(db_url, str) and not db_url.startswith(("sqlite://", "postgresql")):
        db_url = f"sqlite:///{db_url}"

    db_url_str = str(db_url)
    is_pg = db_url_str.startswith("postgresql")

    if not is_pg:
        # SQLite: ensure the parent directory exists
        path_part = db_url_str.replace("sqlite:///", "")
        Path(path_part).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(db_url_str)
    else:
        engine = create_engine(
            db_url_str,
            pool_size=5,
            max_overflow=2,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 30},
        )

    _engine = engine
    _create_schema(engine, db_url_str)

    if is_pg:
        _setup_pg_fts(engine)
        PG_FTS_AVAILABLE = True
        _migrate_projects(engine, db_url_str)
    else:
        _check_schema(engine, db_url_str)
        _migrate_projects(engine, db_url_str)
        _create_fts(engine)

    return sessionmaker(bind=engine, expire_on_commit=False)


#: Bounded retry for the *initial* connection only - a managed database can
#: be briefly unreachable right after provisioning (DNS not yet propagated
#: on a platform like Railway) or during its own maintenance blip. A
#: persistent misconfiguration (wrong host, wrong project/network) still
#: surfaces the same fatal error once attempts are exhausted - this never
#: silently swallows a real problem, it only gives a transient one time to
#: heal within a single container lifetime instead of crash-looping on the
#: very first hiccup.
_SCHEMA_CONNECT_ATTEMPTS = 5
_SCHEMA_CONNECT_BASE_DELAY_SECONDS = 2.0


def _create_schema(engine, db_url_str: str) -> None:
    """``Base.metadata.create_all`` with the retry/race handling above."""
    for attempt in range(1, _SCHEMA_CONNECT_ATTEMPTS + 1):
        try:
            Base.metadata.create_all(engine)
            log.info("Schema initialised on %s", engine.dialect.name)
            return
        except OperationalError as exc:
            # Connection-level failure (DNS resolution, refused, timeout) -
            # the class of error a transient provisioning/network blip
            # produces. Retry with backoff; only fatal once exhausted.
            if attempt == _SCHEMA_CONNECT_ATTEMPTS:
                host = _safe_host(db_url_str)
                log.critical(
                    "Schema creation failed for %s after %d attempts: %s",
                    host,
                    _SCHEMA_CONNECT_ATTEMPTS,
                    exc,
                )
                raise SystemExit(1) from exc
            delay = _SCHEMA_CONNECT_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
            log.warning(
                "Schema creation attempt %d/%d could not connect to %s (%s) "
                "- retrying in %.0fs",
                attempt,
                _SCHEMA_CONNECT_ATTEMPTS,
                _safe_host(db_url_str),
                exc,
                delay,
            )
            time.sleep(delay)
        except (IntegrityError, ProgrammingError) as exc:
            # A benign race, not a real failure: on a platform that briefly
            # overlaps the old and new container during a redeploy
            # (Railway), two processes can both run CREATE TABLE against
            # the same fresh Postgres database within the same instant.
            # One wins; the other collides on the catalog's own unique
            # index (pg_type_typname_nsp_index / pg_class - "already
            # exists") rather than failing more legibly. If every table
            # this process expects is now present (created by whichever
            # process won the race), there is nothing actually wrong -
            # proceed instead of crash-looping forever. Not retried - a
            # second attempt can't change whether the tables now exist.
            if _is_concurrent_create_race(exc) and _all_tables_present(engine):
                log.warning(
                    "Schema creation raced with a concurrent process on %s "
                    "(%s) - all tables already present, continuing",
                    _safe_host(db_url_str),
                    type(exc.orig).__name__ if exc.orig else type(exc).__name__,
                )
                return
            host = _safe_host(db_url_str)
            log.critical("Schema creation failed for %s: %s", host, exc)
            raise SystemExit(1) from exc
        except Exception as exc:
            host = _safe_host(db_url_str)
            log.critical("Schema creation failed for %s: %s", host, exc)
            raise SystemExit(1) from exc


def _is_concurrent_create_race(exc: IntegrityError | ProgrammingError) -> bool:
    """True for the specific concurrent-CREATE-TABLE race on Postgres's own
    catalog (pg_type/pg_class unique indexes), never for an unrelated
    integrity/programming error - narrow on purpose (F1.3: named gaps, not
    silent ones swallowing real schema defects)."""
    msg = str(exc.orig if exc.orig else exc).lower()
    return "pg_type_typname_nsp_index" in msg or (
        "already exists" in msg and "duplicate key" in msg
    )


def _all_tables_present(engine) -> bool:
    """Every table this process's models declare already exists (the state
    a winning concurrent CREATE TABLE would have left behind)."""
    existing = set(inspect(engine).get_table_names())
    expected = set(Base.metadata.tables.keys())
    return expected.issubset(existing)


def _safe_host(db_url: str) -> str:
    """Return the host part of a DB URL without credentials."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        return parsed.hostname or db_url[:40]
    except Exception:
        return db_url[:40]


# ---------------------------------------------------------------------------
# PostgreSQL FTS setup
# ---------------------------------------------------------------------------

def _setup_pg_fts(engine) -> None:
    """Add a ``search_vector`` tsvector column to ``papers`` if absent, and
    create a GIN index on it.  Idempotent — safe to call on every boot."""
    with engine.begin() as conn:
        # Check whether the column already exists
        cols = {c["name"] for c in inspect(engine).get_columns("papers")}
        if "search_vector" not in cols:
            conn.execute(text(
                "ALTER TABLE papers ADD COLUMN search_vector tsvector "
                "GENERATED ALWAYS AS ("
                "  to_tsvector('english', "
                "coalesce(title,'') || ' ' || coalesce(abstract,''))"
                ") STORED"
            ))
            log.info("Added search_vector column to papers (PostgreSQL FTS)")
        # GIN index — CREATE INDEX IF NOT EXISTS is safe
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_papers_fts "
            "ON papers USING gin(search_vector)"
        ))


# ---------------------------------------------------------------------------
# SQLite FTS5 setup  (unchanged from original)
# ---------------------------------------------------------------------------

def _create_fts(engine) -> None:
    """Create the paper full-text index (FTS5) for SQLite.

    Degrades to a plain ``paper_chunks`` table if FTS5 is absent.
    """
    global FTS5_AVAILABLE
    with engine.begin() as conn:
        try:
            conn.execute(text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS paper_fts "
                "USING fts5(paper_ref, chunk_idx UNINDEXED, body)"
            ))
            FTS5_AVAILABLE = True
        except Exception:  # noqa: BLE001 — minimal SQLite without FTS5
            FTS5_AVAILABLE = False
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS paper_chunks ("
                "paper_ref TEXT, chunk_idx INTEGER, body TEXT)"
            ))


# ---------------------------------------------------------------------------
# SQLite-only helpers  (schema check + project migration)
# ---------------------------------------------------------------------------

def _check_schema(engine, db_url: str) -> None:
    """Fail loudly at startup when an existing SQLite DB predates the schema.

    Skipped for PostgreSQL — Railway provisions a fresh managed DB so there
    is no risk of a stale volume, and ``create_all`` handles the schema.
    """
    if _is_postgres(engine):
        return

    inspector = inspect(engine)
    problems = []
    for table in Base.metadata.tables.values():
        if not inspector.has_table(table.name):
            continue
        have = {c["name"] for c in inspector.get_columns(table.name)}
        missing = {c.name for c in table.columns} - have
        if missing:
            problems.append(f"table {table.name!r} lacks column(s) {sorted(missing)}")
    if problems:
        raise RuntimeError(
            f"database {db_url!r} predates the current schema: "
            + "; ".join(problems)
            + ". Either point MIDDLEWARE_DB at a fresh file, or reset the "
            "volume: `docker compose down -v`."
        )


def _migrate_projects(engine, db_url: str) -> None:
    """First-boot project adoption (FR-PLAT-1/5).

    The implicit project + its local-identity membership are created on
    *every* backend (not just SQLite): `none`/`token` single-facilitator
    mode and any protocol-loaded study resolve through them, and a fresh
    Railway/PostgreSQL database would otherwise be missing the row its
    studies reference. Orphan-study adoption is SQLite-only (a legacy
    migration; PostgreSQL provisions a clean DB).
    """
    with engine.begin() as conn:
        created_project = _ensure_implicit_project(conn)
        _ensure_implicit_membership(conn)
        if _is_postgres(engine):
            adopted = 0
        else:
            adopted = _adopt_orphan_studies(conn)
    if created_project or adopted:
        log.warning(
            "PROJECT MIGRATION on %s: %s; adopted %d study row(s) into "
            "project 'implicit'. Nothing was destroyed.",
            db_url,
            "created implicit project"
            if created_project
            else "implicit project exists",
            adopted,
        )


def _ensure_implicit_project(conn) -> bool:
    """Create the implicit project row if missing. Returns True if created."""
    row = conn.execute(
        text("SELECT id FROM projects WHERE id = :id"), {"id": IMPLICIT_PROJECT_ID}
    ).first()
    if row is not None:
        return False
    conn.execute(
        text(
            "INSERT INTO projects (id, name, slug, created_by, created_at) "
            "VALUES (:id, :name, :slug, :created_by, :created_at)"
        ),
        {
            "id": IMPLICIT_PROJECT_ID,
            "name": "My project",
            "slug": IMPLICIT_PROJECT_SLUG,
            "created_by": IMPLICIT_IDENTITY_SUB,
            "created_at": "",
        },
    )
    return True


def _ensure_implicit_membership(conn) -> bool:
    """Auto-member the local identity as owner on the implicit project."""
    row = conn.execute(
        text(
            "SELECT project_id FROM memberships "
            "WHERE project_id = :p AND identity_sub = :s"
        ),
        {"p": IMPLICIT_PROJECT_ID, "s": IMPLICIT_IDENTITY_SUB},
    ).first()
    if row is not None:
        return False
    conn.execute(
        text(
            "INSERT INTO memberships "
            "(project_id, identity_sub, role, invited_by, joined_at) "
            "VALUES (:p, :s, :r, :ib, :ja)"
        ),
        {
            "p": IMPLICIT_PROJECT_ID,
            "s": IMPLICIT_IDENTITY_SUB,
            "r": "owner",
            "ib": "",
            "ja": "",
        },
    )
    return True


def _adopt_orphan_studies(conn) -> int:
    """Adopt every studies row with a null/empty project_id into the implicit
    project.  Returns the count adopted."""
    result = conn.execute(
        text(
            "UPDATE studies SET project_id = :p "
            "WHERE project_id IS NULL OR project_id = ''"
        ),
        {"p": IMPLICIT_PROJECT_ID},
    )
    return int(result.rowcount or 0)
