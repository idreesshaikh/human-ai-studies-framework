"""The demo project: one fully-built study anybody can look at."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from middleware.db import (
    Project,
    ProtocolDraftRow,
    SessionOpen,
    Study,
    make_session_factory,
)

#: The demo study's own protocol, kept beside the sample sessions it describes.
#: Without it the demo can never resolve a protocol at all: ``_resolve_study_
#: protocol`` looks for an approved snapshot, then a compiled draft, then the
#: boot protocol — and the boot protocol (when one is loaded) is ``pilot-2026``,
#: a different study id. So every panel that gates on "has a compiled protocol"
#: — the whole Data tab, Planning, the status endpoint — returned 404 on the one
#: study that exists to show them populated.
DEMO_PROTOCOL_PATH = (
    Path(__file__).resolve().parents[2] / "sample-data" / "demo-protocol.yaml"
)

DEMO_PROJECT_ID = "demo"
DEMO_PROJECT_SLUG = "demo"
DEMO_PROJECT_NAME = "Demo project"
DEMO_STUDY_ID = "ai-and-developer-productivity"

# Kept in step with ``middleware/sample-data/*.jsonl`` — a session id here that the
# seeder never posts is simply an empty mapping, which is harmless.
DEMO_SESSION_IDS = ("S-sample-001", "S-sample-002", "S-sample-003")

DEMO_OWNER_SUB = "demo"


def seed_demo(db_url: str, *, now: str = "") -> dict:
    """Create (or confirm) the demo project, study, and session mappings."""
    factory = make_session_factory(db_url)
    with factory() as s:
        created = _seed(s, now)
        s.commit()
    return created


def _seed(s: Session, now: str) -> dict:
    made: dict = {"project": False, "study": False, "sessions": 0, "protocol": False}

    project = s.get(Project, DEMO_PROJECT_ID)
    if project is None:
        s.add(
            Project(
                id=DEMO_PROJECT_ID,
                name=DEMO_PROJECT_NAME,
                slug=DEMO_PROJECT_SLUG,
                created_by=DEMO_OWNER_SUB,
                created_at=now,
            )
        )
        s.flush()
        made["project"] = True

    # Read access is granted to every authenticated identity in authz, so the demo needs
    # no provisioning and can never be written to.

    study = s.get(Study, DEMO_STUDY_ID)
    if study is None:
        s.add(
            Study(
                id=DEMO_STUDY_ID,
                project_id=DEMO_PROJECT_ID,
                protocol_version="",
                data_path="",
            )
        )
        s.flush()
        made["study"] = True

    # The protocol is what makes the demo "one fully-built study anybody can
    # look at" rather than a study whose data exists but can never surface.
    # Written as a compiled draft, the same row the design conversation's own
    # approve step writes, so the demo reaches the UI through the ordinary path
    # rather than a special case.
    if s.get(ProtocolDraftRow, DEMO_STUDY_ID) is None and DEMO_PROTOCOL_PATH.is_file():
        s.add(
            ProtocolDraftRow(
                study_id=DEMO_STUDY_ID,
                yaml=DEMO_PROTOCOL_PATH.read_text(),
                compilation_id="",
                updated_at=now,
            )
        )
        made["protocol"] = True

    existing = set(
        s.scalars(
            select(SessionOpen.session_id).where(
                SessionOpen.session_id.in_(DEMO_SESSION_IDS)
            )
        )
    )
    for session_id in DEMO_SESSION_IDS:
        if session_id in existing:
            continue
        s.add(
            SessionOpen(
                session_id=session_id,
                study_id=DEMO_STUDY_ID,
                protocol_version=1,
                opened_at=now,
            )
        )
        made["sessions"] += 1

    return made
