"""The demo project: one fully-built study anybody can look at."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from middleware.db import Project, SessionOpen, Study, make_session_factory

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
    made: dict = {"project": False, "study": False, "sessions": 0}

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
