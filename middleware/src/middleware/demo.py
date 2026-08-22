"""The demo project: one fully-built study anybody can look at."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from middleware.db import (
    CORPUS_STUDY_ID,
    ConversationTurn,
    DesignMoveRow,
    Paper,
    PaperLink,
    Project,
    ProtocolDraftRow,
    SessionOpen,
    Study,
    make_session_factory,
)

#: The demo study's own protocol, kept beside the sample sessions it describes.
#: Without it the demo can never resolve a protocol at all: ``_resolve_study_
#: protocol`` looks for an approved snapshot, then a compiled draft, then the
#: boot protocol  -  and the boot protocol (when one is loaded) is ``pilot-2026``,
#: a different study id. So every panel that gates on "has a compiled protocol"
#:  -  the whole Data tab, Planning, the status endpoint  -  returned 404 on the one
#: study that exists to show them populated.
DEMO_PROTOCOL_PATH = (
    Path(__file__).resolve().parents[2] / "sample-data" / "demo-protocol.yaml"
)

DEMO_PROJECT_ID = "demo"
DEMO_PROJECT_SLUG = "demo"
DEMO_PROJECT_NAME = "Demo project"
DEMO_STUDY_ID = "demo-study"

# Kept in step with ``middleware/sample-data/*.jsonl``  -  a session id here that the
# seeder never posts is simply an empty mapping, which is harmless.
DEMO_SESSION_IDS = (
    "S-sample-001",
    "S-sample-002",
    "S-sample-003",
    "S-sample-004",
    "S-sample-005",
    "S-sample-006",
    "S-sample-007",
    "S-sample-008",
    "S-sample-009",
    "S-sample-010",
    "S-sample-011",
)

DEMO_OWNER_SUB = "demo"

DEMO_LIBRARY_REFS = (
    "corpus:trust-in-ai-code-generation",
    "corpus:metr-early-2025-dev-productivity",
    "corpus:guidelines-empirical-llm-se",
    "corpus:insecure-code-with-ai-assistants",
    "corpus:realhumaneval",
)

DEMO_RECOMMENDATIONS = [
    {
        "ref": "corpus:trust-in-ai-code-generation",
        "confidence": 0.98,
        "title": "Investigating and Designing for Trust in AI-powered Code Generation",
        "year": 2024,
        "venue": "Empirical Software Engineering",
        "matchReason": (
            "Measures whether developers verify AI-generated code before accepting it."
        ),
    },
    {
        "ref": "corpus:metr-early-2025-dev-productivity",
        "confidence": 0.94,
        "title": "Measuring the Impact of Early-2025 AI on Developer Productivity",
        "year": 2025,
        "venue": "METR",
        "matchReason": (
            "Pairs perceived productivity with observed task completion "
            "and correctness."
        ),
    },
]


def seed_demo(db_url: str, *, now: str = "") -> dict:
    """Create (or confirm) the demo project, study, and session mappings."""
    factory = make_session_factory(db_url)
    with factory() as s:
        created = _seed(s, now)
        s.commit()
    return created


def _seed(s: Session, now: str) -> dict:
    made: dict = {
        "project": False,
        "study": False,
        "sessions": 0,
        "protocol": False,
        "papers": 0,
        "conversation": False,
    }

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

    corpus_papers = {
        p.paper_ref: p
        for p in s.scalars(
            select(Paper).where(
                Paper.study_id == CORPUS_STUDY_ID,
                Paper.paper_ref.in_(DEMO_LIBRARY_REFS),
            )
        )
    }
    existing_refs = set(
        s.scalars(select(Paper.paper_ref).where(Paper.study_id == DEMO_STUDY_ID))
    )
    for ref in DEMO_LIBRARY_REFS:
        source = corpus_papers.get(ref)
        if source is None or ref in existing_refs:
            continue
        s.add(
            Paper(
                study_id=DEMO_STUDY_ID,
                paper_ref=source.paper_ref,
                title=source.title,
                authors=source.authors,
                year=source.year,
                venue=source.venue,
                abstract=source.abstract,
                doi=source.doi,
                arxiv_id=source.arxiv_id,
                url=source.url,
                item_type=source.item_type,
                source="demo",
                s2_id=source.s2_id,
                citation_count=source.citation_count,
                full_text=source.full_text,
                tier=source.tier,
                score=source.score,
                added_via="demo-seed",
                added_at=now,
            )
        )
        for target in ("researchQuestions", "design", "measures"):
            s.add(PaperLink(study_id=DEMO_STUDY_ID, paper_ref=ref, target=target))
        made["papers"] += 1

    if s.scalar(
        select(ConversationTurn.id).where(ConversationTurn.study_id == DEMO_STUDY_ID)
    ) is None:
        researcher_id = "demo-turn-researcher"
        platform_id = "demo-turn-platform"
        s.add(
            ConversationTurn(
                id=researcher_id,
                study_id=DEMO_STUDY_ID,
                seq=1,
                role="researcher",
                author="Demo Researcher",
                text=(
                    "I want to know whether AI assistance changes developer "
                    "productivity and how carefully developers review the code it "
                    "suggests."
                ),
                retrieved_refs=[],
                recommendations=[],
                created_at=now,
                source="demo",
            )
        )
        s.add(
            ConversationTurn(
                id=platform_id,
                study_id=DEMO_STUDY_ID,
                seq=2,
                role="platform",
                author="Platform",
                text=(
                    "Start with a within-subjects comparison: each developer "
                    "completes matched maintenance tasks with AI assistance and "
                    "without it. That lets the comparison use each developer as "
                    "their own control. I would measure task time, correctness, "
                    "and review behaviour. The evidence below is grounded in the "
                    "corpus."
                ),
                retrieved_refs=[r["ref"] for r in DEMO_RECOMMENDATIONS],
                recommendations=DEMO_RECOMMENDATIONS,
                created_at=now,
                source="demo",
            )
        )
        s.add(
            DesignMoveRow(
                id="demo-move-design",
                study_id=DEMO_STUDY_ID,
                turn_id=platform_id,
                seq=1,
                kind="choose-template",
                target="design",
                proposal=(
                    "Use a counterbalanced within-subjects design so each "
                    "developer completes matched tasks in both conditions."
                ),
                patch={"templateId": "within-subjects-crossover-v1", "parameters": {}},
                grounding=[
                    {
                        "ref": "corpus:metr-early-2025-dev-productivity",
                        "confidence": 0.94,
                        "title": (
                            "Measuring the Impact of Early-2025 AI on Developer "
                            "Productivity"
                        ),
                        "year": 2025,
                        "venue": "METR",
                        "why": (
                            "Pairs perceived productivity with observed task "
                            "completion and correctness."
                        ),
                    }
                ],
                status="accepted",
                decided_by="Demo Researcher",
                decided_at=now,
            )
        )
        s.add(
            DesignMoveRow(
                id="demo-move-measure",
                study_id=DEMO_STUDY_ID,
                turn_id=platform_id,
                seq=2,
                kind="add-measure",
                target="measures[]",
                proposal=(
                    "Measure task completion time, correctness, self-reported "
                    "fatigue, and review latency in both conditions."
                ),
                patch={
                    "section": "measures",
                    "op": "append",
                    "value": "task time, correctness, fatigue, and review latency",
                },
                grounding=[
                    {
                        "ref": "corpus:trust-in-ai-code-generation",
                        "confidence": 0.98,
                        "title": (
                            "Investigating and Designing for Trust in AI-powered "
                            "Code Generation"
                        ),
                        "year": 2024,
                        "venue": "Empirical Software Engineering",
                        "why": (
                            "Measures whether developers verify AI-generated code "
                            "before accepting it."
                        ),
                    }
                ],
                status="proposed",
            )
        )
        made["conversation"] = True

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
