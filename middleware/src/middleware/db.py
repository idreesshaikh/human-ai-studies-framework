"""SQLAlchemy models and engine setup."""

import json
import logging
import re
import time
from hashlib import sha256
from pathlib import Path

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Float,
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


IMPLICIT_PROJECT_SLUG = "implicit"
IMPLICIT_PROJECT_ID = "implicit"
IMPLICIT_IDENTITY_SUB = "local"
CORPUS_STUDY_ID = "platform-corpus"


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
    source: Mapped[str] = mapped_column(String, index=True, default="tern")
    seq: Mapped[int] = mapped_column(Integer)
    participant_id: Mapped[str] = mapped_column(String, index=True)
    condition: Mapped[str] = mapped_column(String)
    task_id: Mapped[str] = mapped_column(String, default="", index=True)
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
    study_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
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
    curator_note: Mapped[str] = mapped_column(Text, default="")
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
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
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
    dst_authors: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    dst_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dst_abstract: Mapped[str] = mapped_column(Text, default="")
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


class Project(Base):
    """One research project  -  the scoping root (FR-PLAT-1)."""

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
            "role IN ('owner', 'member')",
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
    """A reusable share link into a project (FR-PLAT-3)."""

    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id"), index=True
    )
    role: Mapped[str] = mapped_column(String)
    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[str] = mapped_column(String, default="")
    expires_at: Mapped[str] = mapped_column(String)
    accepted_at: Mapped[str | None] = mapped_column(String, nullable=True)


class EnrollmentToken(Base):
    """A pairing token binding a study + participant + condition (FR-INST-20)."""

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
    participant_index: Mapped[int] = mapped_column(Integer, default=0)
    condition: Mapped[str] = mapped_column(String)
    grain: Mapped[str] = mapped_column(String)
    # Per-mint capture-config overrides, layered on the protocol-derived defaults at
    # redeem time (FR-INST-20). ``{"toggles": [{"instrument", "path", "value"}, ...]}``.
    capture_overrides: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    credential: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    expires_at: Mapped[str] = mapped_column(String)
    revoked_at: Mapped[str | None] = mapped_column(String, nullable=True)
    redeemed_at: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[str] = mapped_column(String)


class SessionBlock(Base):
    """Which task and condition one session ran under."""

    __tablename__ = "session_blocks"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    participant_id: Mapped[str] = mapped_column(String, index=True)
    block_index: Mapped[int] = mapped_column(Integer, default=0)
    task_id: Mapped[str] = mapped_column(String, default="")
    condition: Mapped[str] = mapped_column(String, default="")
    assigned_at: Mapped[str] = mapped_column(String, default="")


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


class ConversationTurn(Base):
    """One turn of a study's design conversation (FR-CONV-1)."""

    __tablename__ = "conversation_turns"
    __table_args__ = (
        UniqueConstraint("study_id", "seq", name="uq_conversation_turn_seq"),
        UniqueConstraint(
            "study_id", "request_id", name="uq_conversation_turn_request"
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    seq: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String)
    author: Mapped[str] = mapped_column(String, default="")
    text: Mapped[str] = mapped_column(Text, default="")
    retrieved_refs: Mapped[list] = mapped_column(JSON, default=list)
    recommendations: Mapped[list] = mapped_column(JSON, default=list)
    redacted: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, default="")
    # Client-generated idempotency key. A streamed request can be persisted by
    # the server just before a proxy/browser notices the connection failed; the
    # blocking retry must then resolve to this row instead of appending again.
    request_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)


class DesignMoveRow(Base):
    """One platform-proposed protocol change (FR-CONV-1.2)."""

    __tablename__ = "design_moves"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    turn_id: Mapped[str] = mapped_column(
        String, ForeignKey("conversation_turns.id"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer, default=0)
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
    """The study's current compiled draft  -  one row per study."""

    __tablename__ = "protocol_drafts"

    study_id: Mapped[str] = mapped_column(String, primary_key=True)
    yaml: Mapped[str] = mapped_column(Text, default="")
    compilation_id: Mapped[str] = mapped_column(String, default="")
    updated_at: Mapped[str] = mapped_column(String, default="")


class SessionOpen(Base):
    """The protocol version a data-collection session opened under (FR-CONV-4.4)."""

    __tablename__ = "session_opens"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    protocol_version: Mapped[int] = mapped_column(Integer)
    opened_at: Mapped[str] = mapped_column(String)


class UserProfile(Base):
    """A signed-in identity's per-user preferences (FR-OPS-7, D29)."""

    __tablename__ = "user_profiles"

    identity_sub: Mapped[str] = mapped_column(String, primary_key=True)
    prefs: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[str] = mapped_column(String, default="")



# app.py imports and calls them; it never imports ``sqlite_insert`` directly any more.

def _is_postgres(engine) -> bool:
    return engine.dialect.name == "postgresql"


def upsert_do_nothing(engine, model, rows: list[dict]) -> int:
    """INSERT … ON CONFLICT DO NOTHING for the given model rows."""
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
    """INSERT … ON CONFLICT (conflict_cols) DO UPDATE SET update_cols."""
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


FTS5_AVAILABLE: bool = False
PG_FTS_AVAILABLE: bool = False

_engine = None


def get_engine():
    """Return the shared engine (set by ``make_session_factory``)."""
    return _engine


def make_session_factory(db_url: str | Path) -> sessionmaker:
    """Create the schema if needed and return a session factory."""
    global _engine, FTS5_AVAILABLE, PG_FTS_AVAILABLE

    if isinstance(db_url, Path) or (
        isinstance(db_url, str)
        and not db_url.startswith(("sqlite://", "postgresql"))
    ):
        db_url = f"sqlite:///{db_url}"

    db_url_str = str(db_url)
    is_pg = db_url_str.startswith("postgresql")

    if not is_pg:
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
    _migrate_stored_file_study_id(engine)
    _migrate_paper_curator_note(engine)
    _migrate_conversation_recommendations(engine)
    _migrate_conversation_request_id(engine)
    _migrate_paper_edge_authors(engine)
    _migrate_design_move_seq(engine)
    _migrate_enrollment_participant_index(engine)
    _migrate_event_task_id(engine)
    _migrate_invitation_created_at(engine)
    _migrate_enrollment_capture_overrides(engine)
    _migrate_paper_edge_abstract(engine)

    if is_pg:
        _setup_pg_fts(engine)
        PG_FTS_AVAILABLE = True
        _migrate_projects(engine, db_url_str)
    else:
        _check_schema(engine, db_url_str)
        _migrate_projects(engine, db_url_str)
        _create_fts(engine)

    return sessionmaker(bind=engine, expire_on_commit=False)


# A persistent misconfiguration (wrong host, wrong project/network) still surfaces the
# same fatal error once attempts are exhausted - this never silently swallows a real
# problem, it only gives a transient one time to heal within a single container lifetime
# instead of crash-looping on the very first hiccup.
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
            # Not retried - a second attempt can't change whether the tables now exist.
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


def _migrate_stored_file_study_id(engine) -> None:
    """Add ``files.study_id`` if missing (both dialects, idempotent)."""
    with engine.begin() as conn:
        cols = {c["name"] for c in inspect(engine).get_columns("files")}
        if "study_id" not in cols:
            conn.execute(text("ALTER TABLE files ADD COLUMN study_id VARCHAR"))
            log.info("Added study_id column to files (per-study lifecycle scoping)")


def _migrate_enrollment_participant_index(engine) -> None:
    """Add ``enrollment_tokens.participant_index`` if missing (idempotent)."""
    with engine.begin() as conn:
        cols = {c["name"] for c in inspect(engine).get_columns("enrollment_tokens")}
        if "participant_index" in cols:
            return
        conn.execute(
            text(
                "ALTER TABLE enrollment_tokens "
                "ADD COLUMN participant_index INTEGER DEFAULT 0"
            )
        )
        for row in conn.execute(
            text("SELECT id, participant_id FROM enrollment_tokens")
        ).fetchall():
            digits = "".join(ch for ch in (row[1] or "") if ch.isdigit())
            if digits:
                conn.execute(
                    text(
                        "UPDATE enrollment_tokens SET participant_index = :i "
                        "WHERE id = :id"
                    ),
                    {"i": max(int(digits) - 1, 0), "id": row[0]},
                )
        log.info("Added participant_index to enrollment_tokens (counterbalancing)")


def _migrate_event_task_id(engine) -> None:
    """Add ``events.task_id`` if missing (both dialects, idempotent)."""
    with engine.begin() as conn:
        cols = {c["name"] for c in inspect(engine).get_columns("events")}
        if "task_id" not in cols:
            conn.execute(
                text("ALTER TABLE events ADD COLUMN task_id VARCHAR DEFAULT ''")
            )
            log.info("Added task_id column to events (per-task attribution)")


def _migrate_enrollment_capture_overrides(engine) -> None:
    """Add ``enrollment_tokens.capture_overrides`` if missing (idempotent)."""
    with engine.begin() as conn:
        cols = {c["name"] for c in inspect(engine).get_columns("enrollment_tokens")}
        if "capture_overrides" in cols:
            return
        conn.execute(
            text("ALTER TABLE enrollment_tokens ADD COLUMN capture_overrides JSON")
        )
        log.info("Added capture_overrides to enrollment_tokens (mint-time config)")


def _migrate_invitation_created_at(engine) -> None:
    """Add ``invitations.created_at`` if missing (both dialects, idempotent)."""
    with engine.begin() as conn:
        cols = {c["name"] for c in inspect(engine).get_columns("invitations")}
        if "created_at" not in cols:
            conn.execute(text("ALTER TABLE invitations ADD COLUMN created_at VARCHAR"))
            log.info("Added created_at column to invitations (share-link creation)")


def _migrate_paper_curator_note(engine) -> None:
    """Add ``papers.curator_note`` if missing (both dialects, idempotent)."""
    with engine.begin() as conn:
        cols = {c["name"] for c in inspect(engine).get_columns("papers")}
        if "curator_note" not in cols:
            conn.execute(text("ALTER TABLE papers ADD COLUMN curator_note TEXT"))
            log.info("Added curator_note column to papers (abstract enrichment)")


def _migrate_paper_edge_authors(engine) -> None:
    """Add ``paper_edges.dst_authors`` if missing (both dialects, idempotent)."""
    with engine.begin() as conn:
        cols = {c["name"] for c in inspect(engine).get_columns("paper_edges")}
        if "dst_authors" not in cols:
            conn.execute(text("ALTER TABLE paper_edges ADD COLUMN dst_authors JSON"))
            log.info("Added dst_authors column to paper_edges (graph node labels)")


def _migrate_paper_edge_abstract(engine) -> None:
    """Add ``paper_edges.dst_abstract`` for warm suggested-paper previews."""
    with engine.begin() as conn:
        cols = {c["name"] for c in inspect(engine).get_columns("paper_edges")}
        if "dst_abstract" not in cols:
            conn.execute(text("ALTER TABLE paper_edges ADD COLUMN dst_abstract TEXT"))
            log.info("Added dst_abstract column to paper_edges (paper previews)")


def _migrate_conversation_recommendations(engine) -> None:
    """
    Add ``conversation_turns.recommendations`` if missing (both dialects, idempotent).
    """
    with engine.begin() as conn:
        cols = {c["name"] for c in inspect(engine).get_columns("conversation_turns")}
        if "recommendations" not in cols:
            conn.execute(
                text("ALTER TABLE conversation_turns ADD COLUMN recommendations JSON")
            )
            log.info(
                "Added recommendations column to conversation_turns "
                "(literature rail survives a reload)"
            )


def _migrate_conversation_request_id(engine) -> None:
    """Add the nullable streaming idempotency key to conversation turns."""
    with engine.begin() as conn:
        cols = {c["name"] for c in inspect(engine).get_columns("conversation_turns")}
        if "request_id" not in cols:
            conn.execute(
                text("ALTER TABLE conversation_turns ADD COLUMN request_id VARCHAR")
            )
            log.info(
                "Added request_id to conversation_turns "
                "(stream retries are idempotent)"
            )
        # Existing rows have NULL, so this unique index does not collide with
        # the historical record while making all new request ids study-scoped.
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_conversation_turn_request "
                "ON conversation_turns (study_id, request_id)"
            )
        )


def _migrate_design_move_seq(engine) -> None:
    """Add ``design_moves.seq`` if missing (both dialects, idempotent)."""
    with engine.begin() as conn:
        cols = {c["name"] for c in inspect(engine).get_columns("design_moves")}
        if "seq" in cols:
            return
        conn.execute(text("ALTER TABLE design_moves ADD COLUMN seq INTEGER DEFAULT 0"))
        for (move_id,) in conn.execute(text("SELECT id FROM design_moves")).all():
            m = re.search(r"-m(\d+)$", move_id)
            conn.execute(
                text("UPDATE design_moves SET seq = :seq WHERE id = :id"),
                {"seq": int(m.group(1)) if m else 0, "id": move_id},
            )
        log.info("Added seq column to design_moves (stable in-turn move order)")


def _is_concurrent_create_race(exc: IntegrityError | ProgrammingError) -> bool:
    """
    True for the specific concurrent-CREATE-TABLE race on Postgres's own catalog
    (pg_type/pg_class unique indexes), never for an unrelated integrity/programming
    error - narrow on purpose (F1.3: named gaps, not silent ones swallowing real schema
    defects).
    """
    msg = str(exc.orig if exc.orig else exc).lower()
    return "pg_type_typname_nsp_index" in msg or (
        "already exists" in msg and "duplicate key" in msg
    )


def _all_tables_present(engine) -> bool:
    """
    Every table this process's models declare already exists (the state a winning
    concurrent CREATE TABLE would have left behind).
    """
    existing = set(inspect(engine).get_table_names())
    expected = set(Base.metadata.tables.keys())
    return expected.issubset(existing)


def _safe_host(db_url: str) -> str:
    """Return the host part of a DB URL without credentials."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        return parsed.hostname or db_url[:40]
    except Exception:  # noqa: BLE001 - host is diagnostics only; fall back to a prefix
        return db_url[:40]


def _setup_pg_fts(engine) -> None:
    """
    Add a ``search_vector`` tsvector column to ``papers`` if absent, and create a GIN
    index on it.
    """
    with engine.begin() as conn:
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
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_papers_fts "
            "ON papers USING gin(search_vector)"
        ))


def _create_fts(engine) -> None:
    """Create the paper full-text index (FTS5) for SQLite."""
    global FTS5_AVAILABLE
    with engine.begin() as conn:
        try:
            conn.execute(text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS paper_fts "
                "USING fts5(paper_ref, chunk_idx UNINDEXED, body)"
            ))
            FTS5_AVAILABLE = True
        except Exception:  # noqa: BLE001  -  minimal SQLite without FTS5
            FTS5_AVAILABLE = False
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS paper_chunks ("
                "paper_ref TEXT, chunk_idx INTEGER, body TEXT)"
            ))


def _check_schema(engine, db_url: str) -> None:
    """Fail loudly at startup when an existing SQLite DB predates the schema."""
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
    """First-boot project adoption (FR-PLAT-1/5)."""
    with engine.begin() as conn:
        created_project = _ensure_implicit_project(conn)
        _ensure_implicit_membership(conn)
        adopted = 0 if _is_postgres(engine) else _adopt_orphan_studies(conn)
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
    """Create the implicit project row if missing."""
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
    """
    Adopt every studies row with a null/empty project_id into the implicit project.
    """
    result = conn.execute(
        text(
            "UPDATE studies SET project_id = :p "
            "WHERE project_id IS NULL OR project_id = ''"
        ),
        {"p": IMPLICIT_PROJECT_ID},
    )
    return int(result.rowcount or 0)
