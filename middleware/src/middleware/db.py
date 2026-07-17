"""SQLAlchemy models and engine setup.

SQLite in a single file - participants are ≤ dozens, so the DB engine is a
config swap (any SQLAlchemy URL), not a dependency (decision in MP-04).
Idempotency lives in the schema, not in application checks:

- ``events`` is UNIQUE on ``(session_id, source, seq)`` (FR-ING-2) - replays
  are dropped by ``INSERT .. ON CONFLICT DO NOTHING``.
- ``metric_rows`` is UNIQUE on a content hash, since metrics rows carry no
  ``seq``.

``seq`` is a *per-producer* monotonic counter, so idempotency and gap
detection are keyed on ``source`` as well as ``session_id``: one study
session is written by several independent fire-and-forget producers (the
Cognitive Overlay extension, and - from MP-12 - the agent-capture
conversation leg, the workspace snapshotter, the task harness, and the
correlation job). Each owns its own ``seq`` stream, so their events share
the session join key without colliding, and each stream's completeness is
independently checkable (NFR-1/2). The default ``source`` is
``cognitive-overlay`` - the extension's HttpSink envelope value - so
existing single-producer sessions are unchanged.
"""

import json
from hashlib import sha256
from pathlib import Path

from sqlalchemy import (
    JSON,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    inspect,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class Event(Base):
    """One StudyEvent row (extension schema v2: see extension/src/core/types.ts)."""

    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("session_id", "source", "seq", name="uq_session_source_seq"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, index=True)
    #: Producing instrument stream (FR-ING-2): its own ``seq`` counter lives
    #: here. "cognitive-overlay" (extension), "agent-capture"/"workspace-
    #: snapshot"/"task-harness"/"agent-derived" (MP-12).
    source: Mapped[str] = mapped_column(String, index=True, default="cognitive-overlay")
    seq: Mapped[int] = mapped_column(Integer)
    participant_id: Mapped[str] = mapped_column(String, index=True)
    condition: Mapped[str] = mapped_column(String)
    v: Mapped[int] = mapped_column(Integer)
    ts: Mapped[str] = mapped_column(String, index=True)
    mono: Mapped[float] = mapped_column()
    type: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    #: Integrity flags added at ingest (FR-ING-6), e.g. ["unknown-condition"].
    flags: Mapped[list] = mapped_column(JSON, default=list)
    received_at: Mapped[str] = mapped_column(String)


class MetricRow(Base):
    """One static-metrics row (function- or file-level), as ingested JSONL."""

    __tablename__ = "metric_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    #: 'function_metrics' | 'file_metrics'
    table: Mapped[str] = mapped_column(String)
    session_id: Mapped[str] = mapped_column(String, index=True)
    participant_id: Mapped[str] = mapped_column(String, index=True)
    condition: Mapped[str] = mapped_column(String)
    timestamp: Mapped[str] = mapped_column(String, index=True)
    schema_version: Mapped[int] = mapped_column(Integer)
    row: Mapped[dict] = mapped_column(JSON)
    #: Content hash - metrics rows have no seq, so idempotency hangs here.
    row_hash: Mapped[str] = mapped_column(String, unique=True)
    flags: Mapped[list] = mapped_column(JSON, default=list)
    received_at: Mapped[str] = mapped_column(String)

    @staticmethod
    def hash_row(table: str, row: dict) -> str:
        canonical = json.dumps(row, sort_keys=True, separators=(",", ":"))
        return sha256(f"{table}\n{canonical}".encode()).hexdigest()


class StoredFile(Base):
    """An uploaded artifact (session JSONL, consent PDF, paper) on disk,
    indexed here (FR-ING-5). Content-addressed: same bytes = same record."""

    __tablename__ = "files"
    #: Same bytes under a *different* filename is a distinct artifact: gate
    #: satisfaction is keyed by filename (MP-06), so only the (name, content)
    #: pair deduplicates. The bytes are still stored once, content-addressed.
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
    """One paper in the study's paper set (FR-LIT-5; glossary: Paper).

    Keyed by the canonical ``paperRef`` the protocol's ``literature:`` list
    uses (``doi:...`` / ``arxiv:...``), so protocol links
    join by construction and re-imports are idempotent (FR-ING-2
    discipline). MP-10's FR-LIT-1 ingest (PDF/DOI extraction, Semantic
    Scholar enrichment) extends these rows; this table is its landing
    surface.
    """

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
    #: Where the record came from: "upload"/"id" (MP-10).
    source: Mapped[str] = mapped_column(String, default="id")
    #: Legacy (Zotero importer withdrawn 2026-07-16, FR-LIT-5): the
    #: column stays so pre-existing DBs keep loading; always "" now.
    zotero_key: Mapped[str] = mapped_column(String, default="")
    #: Semantic Scholar paper id (the hash), used to harvest graph edges
    #: (FR-LIT-2). Empty for un-enriched papers.
    s2_id: Mapped[str] = mapped_column(String, default="")
    citation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Extracted PDF text for the assistant's full-text search (FR-LIT-1/4);
    #: never sent anywhere except the FTS index and the assistant's own tool.
    full_text: Mapped[str] = mapped_column(Text, default="")
    added_at: Mapped[str] = mapped_column(String)


class PaperEdge(Base):
    """One citation-graph edge (FR-LIT-2): ``src`` -> ``dst`` of a given kind.

    ``dst`` may be an un-ingested *stub* node (a suggestion the graph offers
    to add). Idempotent on (study, src, dst, kind) so re-harvesting a paper's
    neighbourhood adds no duplicates (FR-ING-2 discipline).
    """

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
    #: 'references' | 'citations' | 'recommendations'
    kind: Mapped[str] = mapped_column(String)
    #: Denormalized stub-node metadata so a suggestion renders without a
    #: separate fetch (title/year only - never full text for un-ingested).
    dst_title: Mapped[str] = mapped_column(String, default="")
    dst_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dst_citation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PaperLink(Base):
    """A paper ↔ protocol-element link (FR-LIT-3): the citable origin of an
    RQ, instrument, metric, or recipe (e.g. Miller's Law → parameter_count).

    ``target`` is a free string in the protocol's justification vocabulary
    (``RQ-P2``, ``instrument:static-metrics``, ``metric:parameter_count``,
    ``recipe:ziegler-acceptance-rate``). Seeded from the protocol's
    ``literature:`` list and editable in the detail drawer.
    """

    __tablename__ = "paper_links"
    __table_args__ = (
        UniqueConstraint("study_id", "paper_ref", "target", name="uq_paper_link"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    paper_ref: Mapped[str] = mapped_column(String, index=True)
    target: Mapped[str] = mapped_column(String)


class S2Cache(Base):
    """Cached Semantic Scholar responses (D8, NFR-7): the graph renders
    offline after the first fetch. Keyed by request URL."""

    __tablename__ = "s2_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String, unique=True)
    body: Mapped[dict] = mapped_column(JSON)
    fetched_at: Mapped[str] = mapped_column(String)


class Finding(Base):
    """Operational-findings log (FR-META-1): the framework's own defects as
    data. Each finding names the ``kind`` of defect and the ``requirement_id``
    whose violation it evidences (RQ-F2), and carries a ``status`` so the
    retrospective can cite still-open ones (MP-11).
    """

    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    #: Defect class: 'seq-gap' | 'integrity-flag' | 'requires-fail' |
    #: 'gate-block' | 'protocol-validation' | 'facilitator' | ''.
    kind: Mapped[str] = mapped_column(String, default="", index=True)
    requirement_id: Mapped[str] = mapped_column(String, default="")
    message: Mapped[str] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String, default="open")  # open | resolved


class RecipeRun(Base):
    """One recorded analysis-recipe run (posted by `analysis run`, MP-07).

    The dashboard's task board projects un-run-recipe cards from these rows
    (FR-DASH-7); the analysis runner records best-effort - an offline
    middleware never blocks an analysis.
    """

    __tablename__ = "recipe_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    recipe_id: Mapped[str] = mapped_column(String, index=True)
    #: RQ ids the recipe answers, as reported by the runner.
    answers: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String, default="ok")
    note: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[str] = mapped_column(String)


class TaskCard(Base):
    """Manual task-board card (consumed by the dashboard, MP-06)."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="open")  # open | done
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(String)


def make_session_factory(db_path: Path | str) -> sessionmaker:
    """Create the schema if needed and return a session factory."""
    if isinstance(db_path, Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    _check_schema(engine, db_path)
    _create_fts(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _check_schema(engine, db_path: Path | str) -> None:
    """Fail LOUDLY at startup when an existing database predates the current
    table shape (``create_all`` never alters existing tables).

    Without this, a stale file - e.g. a compose ``study-data`` volume created
    before MP-12 added ``events.source`` - passes ``/health`` and then 500s
    on the first ingest, which reads as silent data loss to a sensor
    (NFR-1/NFR-2: failures must be visible and diagnosable, never quiet).
    Nothing is migrated or deleted automatically - participant data is only
    ever removed by an explicit human action.
    """
    inspector = inspect(engine)
    problems = []
    for table in Base.metadata.tables.values():
        have = {c["name"] for c in inspector.get_columns(table.name)}
        missing = {c.name for c in table.columns} - have
        if missing:
            problems.append(f"table {table.name!r} lacks column(s) {sorted(missing)}")
    if problems:
        raise RuntimeError(
            f"database {db_path} predates the current schema: "
            + "; ".join(problems)
            + ". It was created by an older middleware version. Either point "
            "MIDDLEWARE_DB at a fresh file, or - if the data is disposable "
            "demo seed (DR-05) - reset it: locally delete the file; under "
            "docker compose run `docker compose down -v`."
        )


#: Whether the SQLite build has FTS5. Set on first ``_create_fts`` call; the
#: assistant's ``search_papers`` tool falls back to a LIKE scan when False
#: (FR-LIT-4 works even on a minimal SQLite).
FTS5_AVAILABLE = False


def _create_fts(engine) -> None:
    """Create the paper full-text index (FTS5) - the assistant's
    ``search_papers`` corpus (FR-LIT-4). Chunked so citations can point at a
    section (``[paper-ref §chunk]``). Degrades to a LIKE scan if FTS5 is
    absent (see ``paper_index``)."""
    global FTS5_AVAILABLE
    from sqlalchemy import text

    with engine.begin() as conn:
        try:
            conn.execute(
                text(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS paper_fts "
                    "USING fts5(paper_ref, chunk_idx UNINDEXED, body)"
                )
            )
            FTS5_AVAILABLE = True
        except Exception:  # noqa: BLE001 - minimal SQLite without FTS5
            FTS5_AVAILABLE = False
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS paper_chunks ("
                    "paper_ref TEXT, chunk_idx INTEGER, body TEXT)"
                )
            )
