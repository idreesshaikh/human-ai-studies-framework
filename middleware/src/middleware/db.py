"""SQLAlchemy models and engine setup.

SQLite in a single file - participants are ≤ dozens, so the DB engine is a
config swap (any SQLAlchemy URL), not a dependency (decision in).
Idempotency lives in the schema, not in application checks:

- ``events`` is UNIQUE on ``(session_id, source, seq)`` (FR-ING-2) - replays
  are dropped by ``INSERT .. ON CONFLICT DO NOTHING``.
- ``metric_rows`` is UNIQUE on a content hash, since metrics rows carry no
  ``seq``.

``seq`` is a *per-producer* monotonic counter, so idempotency and gap
detection are keyed on ``source`` as well as ``session_id``: one study
session is written by several independent fire-and-forget producers (the
Cognitive Overlay extension, and - from - the agent-capture
conversation leg, the workspace snapshotter, the task harness, and the
correlation job). Each owns its own ``seq`` stream, so their events share
the session join key without colliding, and each stream's completeness is
independently checkable (NFR-1/2). The default ``source`` is
``cognitive-overlay`` - the extension's HttpSink envelope value - so
existing single-producer sessions are unchanged.
"""

import json
import logging
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
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

log = logging.getLogger("middleware.db")

#: The one auto-created project in self-hosted (none/token) modes, and the
#: adoptor for orphan studies on first boot after upgrade (FR-PLAT-5). One
#: code path everywhere - zero ``if multi_tenant`` conditionals.
IMPLICIT_PROJECT_SLUG = "implicit"
IMPLICIT_PROJECT_ID = "implicit"
IMPLICIT_IDENTITY_SUB = "local"

#: The shared public demo project (FR-PLAT-4). Read-only ``viewer`` role,
#: reseeded on boot when ``DEMO_MODE=1`` (D25 Render posture).
DEMO_PROJECT_SLUG = "demo"

#: The platform-level corpus scope (FR-LIT-8). Corpus papers are shared
#: knowledge every design conversation can retrieve and cite - not any one
#: study's evidence - so they land under this reserved study id rather than
#: a researcher's study. The importer (``corpus_importer``) owns these rows;
#: study paper sets (FR-LIT-5) are untouched.
CORPUS_STUDY_ID = "platform-corpus"

#: The three roles on a project (fr-plat.md §2). Kept here (not just in
#: ``authz.py``) so the DB CHECK constraint and the enum cannot drift apart.
ROLES = ("owner", "researcher", "viewer")


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
    #: snapshot"/"task-harness"/"agent-derived".
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
    #: satisfaction is keyed by filename, so only the (name, content)
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
    """One paper in the study's paper set (glossary: Paper).

    Keyed by the canonical ``paperRef`` the protocol's ``literature:`` list
    uses (``doi:...`` / ``arxiv:...``), so protocol links
    join by construction and re-imports are idempotent (FR-ING-2
    discipline). The FR-LIT-1 ingest (PDF/DOI extraction, Semantic
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
    #: Where the record came from: "upload"/"id".
    source: Mapped[str] = mapped_column(String, default="id")
    #: Legacy column kept so pre-existing databases keep loading; always "".
    zotero_key: Mapped[str] = mapped_column(String, default="")
    #: Semantic Scholar paper id (the hash), used to harvest graph edges
    #: (FR-LIT-2). Empty for un-enriched papers.
    s2_id: Mapped[str] = mapped_column(String, default="")
    citation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Extracted PDF text for the assistant's full-text search (FR-LIT-1/4);
    #: never sent anywhere except the FTS index and the assistant's own tool.
    full_text: Mapped[str] = mapped_column(Text, default="")
    #: Corpus provenance (FR-LIT-8): 'A' (hand-curated seed), 'B' (harvested),
    #: or 'study' (researcher-ingested, the FR-LIT-1 path). A paper lives in
    #: exactly one tier; the constellation renders them distinguishably (F8.4).
    tier: Mapped[str] = mapped_column(String, default="study", index=True)
    #: How the paper entered a study's set (FR-LIT-9.3): '' (direct ingest)
    #: or 'match' (accepted recommendation). The match reason is *kept* -
    #: it is elicitation evidence, not UI chrome.
    added_via: Mapped[str] = mapped_column(String, default="")
    match_reason: Mapped[str] = mapped_column(Text, default="")
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
    retrospective can cite still-open ones.
    """

    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    #: Defect class: 'seq-gap' | 'integrity-flag' | 'requires-fail' |
    #: 'gate-block' | 'protocol-validation' | 'facilitator' | 'feedback' | ''.
    #: 'feedback' rows are platform feedback marked in a design conversation
    #: (FR-CONV-5.1); their ``context`` carries a ``conversationLocus`` — the
    #: exact study/turn that motivated the finding. The platform grows its own
    #: SRS from its users' conversations exactly as a study grows from its
    #: researcher's (the self-application is the thesis point).
    kind: Mapped[str] = mapped_column(String, default="", index=True)
    requirement_id: Mapped[str] = mapped_column(String, default="")
    message: Mapped[str] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String, default="open")  # open | resolved


class RecipeRun(Base):
    """One recorded analysis-recipe run (posted by `analysis run`).

    The platform's task board projects un-run-recipe cards from these rows
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
    """Manual task-board card (consumed by the platform)."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="open")  # open | done
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(String)


# ---------------------------------------------------- platform layer
#
# Projects, memberships, invitations, and a reified study row (FR-PLAT-1/2/3).
# "Study" was previously a *concept* derived from the loaded protocol
# (``check.study_id``); reifies it as a row so the project choke point
# (``authz.require_project_for_study``) can resolve study_id -> project ->
# membership in one place. Papers/edges/links/recipe_runs already carried a
# ``study_id`` and inherit scoping through this join; events/metric_rows/files/
# findings/tasks were never study-scoped at the column level and stay that way
# - the scope *check* lives in the dependency, not in every query's WHERE.


class Project(Base):
    """One research project - the scoping root (FR-PLAT-1).

    Everything belongs to a project: studies, paper sets, curated datasets,
    conversations, findings. The ``implicit`` project (one per deployment)
    is the self-hosted continuity row - real, invisible in UI (FR-PLAT-5).
    """

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    slug: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_by: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[str] = mapped_column(String)


class Membership(Base):
    """One identity's role on one project (FR-PLAT-2).

    ``role`` is owner/researcher/viewer (the CHECK constraint mirrors the
    ``authz.Role`` enum). The permission matrix is enforced server-side at
    the choke point; the UI merely reflects it.
    """

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
    """A pending email-link invitation (FR-PLAT-3).

    Single-use, expiring, role pre-assigned. ``token`` is unique; accepting
    binds ``sub`` -> membership through the sign-in gate (FR-OPS-5). Email
    delivery is a pluggable provider with a copy-link fallback.
    """

    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id"), index=True
    )
    email: Mapped[str] = mapped_column(String, default="")
    role: Mapped[str] = mapped_column(String)
    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    expires_at: Mapped[str] = mapped_column(String)
    #: Set when the invitation is consumed; NULL while pending.
    accepted_at: Mapped[str | None] = mapped_column(String, nullable=True)


class Study(Base):
    """A reified study row (FR-PLAT-1). The bridge studies -> projects.

    Pre- ``study_id`` was a free string on papers/edges/links/recipe
    runs, validated only against the loaded protocol. reifies it so
    every study-scoped query can resolve to a project through one choke
    point. The row is created lazily from the loaded protocol at boot and
    on first reference; existing study_id strings are adopted into the
    implicit project on first start after upgrade.
    """

    __tablename__ = "studies"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id"), index=True
    )
    protocol_version: Mapped[str] = mapped_column(String, default="")
    #: 'drafting' | 'open' | 'paused' | 'closed' (protocol lifecycle).
    phase: Mapped[str] = mapped_column(String, default="")
    data_path: Mapped[str] = mapped_column(String, default="")


class MiningJob(Base):
    """A curated-dataset mining job (FR-CUR-2).

    Runs as a background task inside the one FastAPI process (NFR-7 - no
    worker fleet). State, cursor, and coverage persist here so an interrupted
    job resumes from its last checkpoint rather than restarting
    (``state-machines.md`` §3):
    ``declared -> running <-> paused_rate_limited / interrupted -> gated ->
    complete | failed_gate``. The ``cursor`` is the adapter's opaque resume
    point (persisted verbatim); ``coverage`` accumulates requested/retrieved/
    dropped for the threats record.
    """

    __tablename__ = "mining_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    source: Mapped[str] = mapped_column(String, default="github")
    #: declared | running | paused_rate_limited | interrupted | gated |
    #: complete | failed_gate
    state: Mapped[str] = mapped_column(String, default="declared", index=True)
    #: The adapter's opaque resume cursor (JSON), or NULL before the first
    #: checkpoint. Resuming replays from here - the entire resume story.
    cursor: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    #: {requested, retrieved, dropped: {reason: count}}.
    coverage: Mapped[dict] = mapped_column(JSON, default=dict)
    #: Heuristic ids (``id@version``) that fired during the run.
    fired_heuristics: Mapped[list] = mapped_column(JSON, default=list)
    #: Per-dataset salt for pseudonymization - server-side, never exported.
    salt: Mapped[str] = mapped_column(String, default="")
    #: Plain-language status for the UI (e.g. a rate-limit pause message).
    status_message: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[str] = mapped_column(String, default="")
    updated_at: Mapped[str] = mapped_column(String, default="")


class CuratedDataset(Base):
    """A curated dataset + its mandatory validity-threats record (FR-CUR-3).

    Produced when a mining job reaches ``gated``. The threats record is a
    lifecycle gate artifact: the study cannot enter ``analysis`` without it
    (F3.2). Its contents are injected verbatim into the report/paper-draft
    threats sections (F3.1).
    """

    __tablename__ = "curated_datasets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    job_id: Mapped[str] = mapped_column(String, index=True)
    #: The full validity-threats record (fr-cur.md §4).
    threats_record: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    #: Event counts by type, for the dataset browser.
    event_counts: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String, default="")


# ---------------------------------------------------- conversation layer
#
# The design conversation as the elicitation record (FR-CONV-6): append-only
# turns, design moves, compilations, and approvals. Decisions are never
# silently unmade - a redacted turn leaves a tombstone, moves keep their
# accept/reject history, and a compiled diff applies only through a recorded
# approval row (FR-CONV-3.3). All rows are study-scoped and reach projects
# through the ``authz.require_project_for_study`` choke point.


class ConversationTurn(Base):
    """One turn of a study's design conversation (FR-CONV-1).

    ``retrieved_refs`` records every paper/template ref this exchange's
    tools returned - the cite-what-you-retrieved boundary (FR-CONV-2.2):
    a design move may only carry grounding drawn from this set, and the
    grep-the-output test (F2.1) asserts exactly that against these rows.
    """

    __tablename__ = "conversation_turns"
    __table_args__ = (
        UniqueConstraint("study_id", "seq", name="uq_conversation_turn_seq"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    #: Thread order; append-only, never renumbered.
    seq: Mapped[int] = mapped_column(Integer)
    #: 'researcher' | 'platform' (glossary voice; the platform speaks first
    #: person, FR-CONV-1.2 shows attribution per turn).
    role: Mapped[str] = mapped_column(String)
    author: Mapped[str] = mapped_column(String, default="")
    text: Mapped[str] = mapped_column(Text, default="")
    #: Refs returned by tools *in this exchange* (papers, templates).
    retrieved_refs: Mapped[list] = mapped_column(JSON, default=list)
    #: Tombstone (FR-CONV-6.3): 1 = text redacted; the row, its moves, and
    #: any approvals referencing them stay intact and verifiable.
    redacted: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String)


class DesignMoveRow(Base):
    """One platform-proposed protocol change (FR-CONV-1.2, glossary:
    design move), individually accepted/rejected. ``patch`` is the plain
    (section, op, value) change the deterministic compiler applies;
    caution moves carry none. ``grounding`` is the citation set or [] -
    an empty set compiles with an explicit ``grounding: none`` trace
    (FR-CONV-2 F2.3), honesty recorded, not just displayed."""

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
    #: 'proposed' | 'accepted' | 'rejected' - the decision history is part
    #: of the elicitation record; rows are never deleted.
    status: Mapped[str] = mapped_column(String, default="proposed")
    decided_by: Mapped[str] = mapped_column(String, default="")
    decided_at: Mapped[str] = mapped_column(String, default="")


class Compilation(Base):
    """One deterministic compile of accepted moves into a protocol draft
    diff (FR-CONV-3). Stored *unapplied*; only an ``approvals`` row (via
    the approve endpoint's role check) sets ``applied_at`` and advances
    the study's current draft - no other code path writes a draft
    (F3.3). ``hunk_trace`` maps every diff hunk back to the move (and so
    the grounding) that produced it (FR-CONV-3.2, the F6.1 chain)."""

    __tablename__ = "compilations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    #: sha256 of the base draft YAML ('' base = empty draft) - replay
    #: identity for the F3.1 determinism check.
    base_sha256: Mapped[str] = mapped_column(String, default="")
    draft_yaml: Mapped[str] = mapped_column(Text, default="")
    diff: Mapped[str] = mapped_column(Text, default="")
    #: [{"moveId": ..., "hunk": ..., "lines": [...]}] - per-hunk trace.
    hunk_trace: Mapped[list] = mapped_column(JSON, default=list)
    #: The accepted move ids folded, in application order.
    move_ids: Mapped[list] = mapped_column(JSON, default=list)
    #: `protocol validate` + recipe pre-check output (FR-CONV-3.2); a
    #: schema-breaking move bounces back as a conversation turn, so these
    #: are threaded, never silent.
    errors: Mapped[list] = mapped_column(JSON, default=list)
    #: Mandatory protocol slots still empty - named, not silent (F1.3).
    unresolved: Mapped[list] = mapped_column(JSON, default=list)
    valid: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String)
    #: Set only by the approve endpoint (FR-CONV-3.3); '' = never applied.
    applied_at: Mapped[str] = mapped_column(String, default="")


class ApprovalEvent(Base):
    """The audit row behind every applied diff (FR-CONV-3.3/F3.3): who
    approved which compilation, holding which role, when. Append-only."""

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
    """The study's *current* compiled draft - one row per study, advanced
    only by an approval (history lives in ``compilations``). The YAML here
    is a draft of the document of record, never the record itself: the
    frozen protocol file stays the sole source of truth (FR-PROT-1)."""

    __tablename__ = "protocol_drafts"

    study_id: Mapped[str] = mapped_column(String, primary_key=True)
    yaml: Mapped[str] = mapped_column(Text, default="")
    compilation_id: Mapped[str] = mapped_column(String, default="")
    updated_at: Mapped[str] = mapped_column(String, default="")


# ---------------------------------------------------- evolution layer
#
# Two loops close here, and they are the same loop at two scales (FR-CONV-4/5).
# *The study evolves*: mid-study changes compile like everything else but route
# through phase-aware amendment rules — version-visible always, consent-gated
# when it matters, never sneaky. *The platform evolves*: researcher feedback
# marked in a turn becomes a Finding (the existing FR-META-1 pipeline) that
# feeds the platform's own retrospective. Cross-project learning aggregates
# anonymous *shape* only — no conversation text, protocol content, or project
# identifier ever leaves a project boundary (FR-CONV-5.3, grep-the-output).
#
# New tables only (never an ALTER on a live table): the loud stale-DB check
# (``_check_schema``) fires on a column missing from an *existing* table, so
# evolution state lives in its own tables and pre- databases keep loading.


class StudyEvolution(Base):
    """One row per study tracking its amendment lifecycle (FR-CONV-4).

    Pre-ethics a study has no row (or ``ethics_approved_at`` empty) and every
    compile-approve is an ordinary draft application (FR-CONV-4.1 — no ceremony
    before ceremony is owed). Ethics approval snapshots the *approved protocol*
    (``approved_yaml`` + ``current_version``): the executed protocol S3 cares
    about. Thereafter each approved compile is an **amendment** diffed against
    this snapshot, and a consent-relevant one sets ``pending_reapproval`` to the
    amendment id — the deterministic gate that pauses *new* data-collection
    sessions until the re-approval artifact is uploaded (F4.1)."""

    __tablename__ = "study_evolution"

    study_id: Mapped[str] = mapped_column(String, primary_key=True)
    #: Set by the ethics-approval endpoint; '' = pre-ethics (ordinary compiles).
    ethics_approved_at: Mapped[str] = mapped_column(String, default="")
    #: The approved protocol snapshot amendments diff against (consent rule).
    approved_yaml: Mapped[str] = mapped_column(Text, default="")
    #: The version sessions run under and dataset/timeline chips render (F4.3).
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    #: Amendment id awaiting an ethics re-approval artifact, or '' when clear.
    #: While set, ``sessions/start`` refuses *new* sessions (F4.1); already-open
    #: sessions and already-collected data are untouched (NFR-1).
    pending_reapproval: Mapped[str] = mapped_column(String, default="")
    updated_at: Mapped[str] = mapped_column(String, default="")


class Amendment(Base):
    """One post-ethics protocol change (FR-CONV-4.2): a version bump plus the
    record S3 relies on — summary, rationale, grounding, approver, timestamp.

    ``consent_relevant`` is decided by the deterministic rule in
    ``evolution.consent_relevance`` (never an LLM judgment): anything touching
    the ethics section, the content policy, or introducing a new data stream
    (a new instrument) is consent-relevant, by rule, testably. A consent-
    relevant amendment carries ``reapproval_artifact``/``reapproved_at`` once
    the updated ethics artifact is uploaded; a non-relevant one (e.g. a
    threshold tweak) needs none and applies from the next session (F4.2)."""

    __tablename__ = "amendments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    compilation_id: Mapped[str] = mapped_column(String, default="")
    from_version: Mapped[int] = mapped_column(Integer)
    to_version: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(Text, default="")
    #: The deterministic plain-language change list (evolution.change_summary),
    #: so the ethics-board delta regenerates from this row alone.
    changes: Mapped[list] = mapped_column(JSON, default=list)
    rationale: Mapped[str] = mapped_column(Text, default="")
    grounding: Mapped[list] = mapped_column(JSON, default=list)
    consent_relevant: Mapped[int] = mapped_column(Integer, default=0)
    #: Why the consent rule fired (or [] when it did not) — the human summary
    #: quotes these verbatim, so the reason is recorded, not re-derived.
    consent_reasons: Mapped[list] = mapped_column(JSON, default=list)
    approved_by: Mapped[str] = mapped_column(String, default="")
    role: Mapped[str] = mapped_column(String, default="")
    #: The uploaded ethics re-approval artifact filename, '' until provided.
    reapproval_artifact: Mapped[str] = mapped_column(String, default="")
    reapproved_at: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[str] = mapped_column(String)


class SessionOpen(Base):
    """The protocol version a data-collection session opened under (FR-CONV-4.4,
    F4.3). Recorded once at ``sessions/start``; never rewritten — a session in
    flight keeps the version it began with even as the study evolves (NFR-1, the
    F4.2 in-flight guarantee). Two sessions under different versions render
    distinguishably in the dataset and timeline from these rows."""

    __tablename__ = "session_opens"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    study_id: Mapped[str] = mapped_column(String, index=True)
    protocol_version: Mapped[int] = mapped_column(Integer)
    opened_at: Mapped[str] = mapped_column(String)


class AggregateShape(Base):
    """One anonymous cross-project usage shape (FR-CONV-5.3): a count keyed by a
    ``metric`` (which templates chosen, which slots end unresolved, where
    conversations stall, which moves get rejected) and an opaque ``key`` drawn
    from a fixed vocabulary — *never* conversation text, protocol content, or a
    project identifier. The grep-the-output CI test asserts exactly that over
    this table (mirroring FR-ETH-4's), so the boundary is enforced on the
    output, not merely intended."""

    __tablename__ = "aggregate_shapes"
    __table_args__ = (UniqueConstraint("metric", "key", name="uq_aggregate_shape"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    #: 'template-chosen' | 'slot-unresolved' | 'conversation-stall' |
    #: 'move-rejected' — the fixed taxonomy, seeded from
    #: ``stalled-biased-confused-rca`` and grown from observed shape.
    metric: Mapped[str] = mapped_column(String, index=True)
    #: An opaque bucket within the metric (a template id, a slot name, a stall
    #: category, a move kind) — vocabulary only, asserted free of PII/text.
    key: Mapped[str] = mapped_column(String)
    count: Mapped[int] = mapped_column(Integer, default=0)
    computed_at: Mapped[str] = mapped_column(String, default="")


def make_session_factory(db_path: Path | str) -> sessionmaker:
    """Create the schema if needed and return a session factory."""
    if isinstance(db_path, Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    _check_schema(engine, db_path)
    _migrate_projects(engine, db_path)
    _create_fts(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _migrate_projects(engine, db_path: Path | str) -> None:
    """First-boot project adoption (FR-PLAT-1, FR-PLAT-5).

    Additive and safe: nothing is destroyed. On the first start after
    upgrade this (1) creates the single ``implicit`` project if missing,
    (2) auto-members the local identity as ``owner`` on it, and (3) adopts
    every ``studies`` row with a null ``project_id`` into it. It announces
    itself with one loud log block - the stale-DB posture, relaxed
    only because nothing is destroyed (roadmap 14 §Slice A step 2).

    Idempotent: re-runs are no-ops. Runs after ``create_all`` and after
    ``_check_schema``, so the ``studies``/``projects``/``memberships``
    tables always exist here.
    """
    with engine.begin() as conn:
        created_project = _ensure_implicit_project(conn)
        _ensure_implicit_membership(conn)
        adopted = _adopt_orphan_studies(conn)
    if created_project or adopted:
        log.warning(
            "PROJECT MIGRATION on %s: %s; adopted %d study row(s) into "
            "project 'implicit' (slug). Nothing was destroyed. One code "
            "path serves self-hosted (none/token) and hosted (clerk) modes.",
            db_path,
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
    """Adopt every studies row with a null project_id into the implicit
    project. Returns the count adopted (0 if the studies table is empty or
    absent - it is created by ``create_all`` just before this runs)."""
    result = conn.execute(
        text(
            "UPDATE studies SET project_id = :p WHERE project_id IS NULL "
            "OR project_id = ''"
        ),
        {"p": IMPLICIT_PROJECT_ID},
    )
    return int(result.rowcount or 0)


def _check_schema(engine, db_path: Path | str) -> None:
    """Fail LOUDLY at startup when an existing database predates the current
    table shape (``create_all`` never alters existing tables).

    Without this, a stale file - e.g. a compose ``study-data`` volume created
    before added ``events.source`` - passes ``/health`` and then 500s
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
