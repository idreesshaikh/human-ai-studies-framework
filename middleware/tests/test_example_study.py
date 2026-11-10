"""
``seed-example``: one labelled synthetic study, written through the real routes.

The contract under test is the honesty one: every seeded row carries the
service's existing synthetic marker, default reads and exports leave the rows
out, and only an explicit ``includeSynthetic`` read (which the Data tab makes
for this study alone) returns them.
"""

import io
import json
import zipfile
from collections import Counter

import pytest
from analysis.outcomes import participant_outcomes
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.db import (
    EnrollmentToken,
    Event,
    MetricRow,
    ProtocolDraftRow,
    SessionBlock,
    SessionOpen,
    Study,
    StudyPlan,
    make_session_factory,
)
from middleware.example_study import (
    COMPLETED_PARTICIPANTS,
    CONDITIONS,
    EXAMPLE_STUDY_ID,
    EXAMPLE_TITLE,
    PLANNED_PARTICIPANTS,
    seed_example,
)
from middleware.settings import Settings
from protocol.loader import validate_protocol
from protocol.measures import validated_responses
from sqlalchemy import func, select

BASE = f"/studies/{EXAMPLE_STUDY_ID}"
SESSIONS = COMPLETED_PARTICIPANTS * 2 + 1
TABLES = (
    Study,
    ProtocolDraftRow,
    StudyPlan,
    EnrollmentToken,
    SessionBlock,
    SessionOpen,
    Event,
    MetricRow,
)


def _settings(tmp_path, name="example") -> Settings:
    return Settings(
        db_path=tmp_path / f"{name}.sqlite3",
        data_dir=tmp_path / "data",
        spa_dist=tmp_path / "no-dist",
        auth="none",
    )


def _counts(settings) -> dict:
    with make_session_factory(settings.db_url)() as s:
        return {
            t.__tablename__: s.scalar(select(func.count()).select_from(t))
            for t in TABLES
        }


def _events(settings) -> list[tuple]:
    with make_session_factory(settings.db_url)() as s:
        return [
            (
                e.session_id,
                e.source,
                e.seq,
                e.participant_id,
                e.condition,
                e.task_id,
                e.ts,
                e.type,
                json.dumps(e.payload, sort_keys=True),
                tuple(e.flags),
                e.received_at,
            )
            for e in s.scalars(
                select(Event).order_by(Event.session_id, Event.source, Event.seq)
            )
        ]


@pytest.fixture()
def seeded(tmp_path):
    settings = _settings(tmp_path)
    result = seed_example(settings)
    assert result["created"] is True
    assert result["sessions"] == SESSIONS
    return settings


@pytest.fixture()
def client(seeded):
    with TestClient(create_app(seeded)) as tc:
        yield tc


def test_outcome_checks_inspect_synthetic_example_without_changing_data(client, seeded):
    before = _events(seeded)
    default = client.get(f"{BASE}/outcome-checks")
    assert default.status_code == 200
    assert default.json()["sessionUnits"] == 0
    assert default.json()["synthetic"] is False
    response = client.get(f"{BASE}/outcome-checks?includeSynthetic=true")
    assert response.status_code == 200
    report = response.json()
    assert report["sessionUnits"] == SESSIONS and report["synthetic"] is True
    assert report["outcomes"]
    assert any(o["observedUnits"] for o in report["outcomes"])
    assert any(o["issues"] for o in report["outcomes"])
    assert _events(seeded) == before
    assert client.get(f"{BASE}/dataset").json()["rows"] == []
    assert (
        client.get(f"{BASE}/outcome-checks?includeSynthetic=invalid").status_code == 422
    )
    blank = client.post(
        "/projects/implicit/studies", json={"name": "No capture protocol"}
    ).json()["id"]
    assert client.get(f"/studies/{blank}/outcome-checks").status_code == 409


def test_seeding_twice_changes_nothing(seeded):
    before = _counts(seeded)
    assert before["studies"] == 1
    assert before["study_plans"] == 1
    assert before["enrollment_tokens"] == PLANNED_PARTICIPANTS
    assert before["session_blocks"] == before["session_opens"] == SESSIONS
    assert before["metric_rows"] == 0
    events = _events(seeded)

    again = seed_example(seeded)

    assert again == {"studyId": EXAMPLE_STUDY_ID, "created": False}
    assert _counts(seeded) == before
    assert _events(seeded) == events


def test_two_fresh_seeds_store_identical_events(tmp_path):
    first, second = _settings(tmp_path, "a"), _settings(tmp_path, "b")
    seed_example(first)
    seed_example(second)
    assert _events(first) == _events(second)


def test_every_seeded_row_carries_the_synthetic_marker(seeded):
    with make_session_factory(seeded.db_url)() as s:
        payloads = list(s.scalars(select(Event.payload)))
        sessions = set(s.scalars(select(Event.session_id)))
        mapped = set(
            s.scalars(
                select(SessionBlock.session_id).where(
                    SessionBlock.study_id == EXAMPLE_STUDY_ID
                )
            )
        )
    assert payloads
    assert all(p.get("synthetic") is True for p in payloads)
    assert sessions == mapped and len(sessions) == SESSIONS


def test_protocol_is_a_valid_v6_example_with_a_saved_plan_and_links(client):
    protocol = client.get(f"{BASE}/protocol").json()["document"]
    assert validate_protocol(protocol) == []
    assert protocol["protocolVersion"] == 6
    assert protocol["study"]["title"] == EXAMPLE_TITLE
    assert "synthetic" in EXAMPLE_TITLE and EXAMPLE_TITLE.startswith("Example")
    assert protocol["conditions"] == CONDITIONS
    assert protocol["participants"]["planned"] == PLANNED_PARTICIPANTS

    plan = client.get(f"{BASE}/plan").json()["plan"]
    assert plan["measureId"] == "first-green-time"
    assert plan["stale"] is False
    assert plan["required"]["totalN"] > 0

    links = client.get(f"{BASE}/enrollment/tokens").json()
    assert len(links) == PLANNED_PARTICIPANTS
    assert Counter(link["status"] for link in links) == {
        "paired": COMPLETED_PARTICIPANTS + 1,
        "unredeemed": PLANNED_PARTICIPANTS - COMPLETED_PARTICIPANTS - 1,
    }

    home = client.get("/projects/implicit").json()
    assert {"id": EXAMPLE_STUDY_ID, "hasProtocol": True} in home["studies"]


def test_default_reads_and_exports_leave_the_synthetic_rows_out(client):
    status = client.get(f"{BASE}/status").json()
    assert status["sessions"] == []
    assert status["syntheticExample"] is True
    assert client.get(f"{BASE}/dataset").json()["rows"] == []
    assert client.get(f"{BASE}/sessions").json() == []
    assert client.get(f"{BASE}/control-arm-audit").json()["sessions"] == []

    res = client.get(f"{BASE}/data-bundle")
    assert res.status_code == 200, res.text
    bundle = zipfile.ZipFile(io.BytesIO(res.content))
    manifest = json.loads(bundle.read("manifest.json"))
    assert manifest["includesSynthetic"] is False
    assert manifest["rows"] == 0 and manifest["tables"] == {}
    assert json.loads(bundle.read("events/all.json"))["rows"] == []
    assert not [n for n in bundle.namelist() if n.endswith(".csv")]
    card = json.loads(bundle.read("design-card.json"))
    assert card["sessionVersions"] == [] and card["audit"]["sessions"] == []


def test_pilot_estimates_and_analysis_never_use_the_synthetic_rows(client):
    rows = client.get(f"{BASE}/dataset?includeSynthetic=true").json()["rows"]
    protocol = client.get(f"{BASE}/protocol").json()["document"]
    assert participant_outcomes(rows, protocol, "task_outcome.firstGreenMs") == {}

    sessions = client.get(f"{BASE}/status?includeSynthetic=true").json()["sessions"]
    tagged = client.post(
        f"{BASE}/sessions/{sessions[0]['sessionId']}/annotation",
        json={"pilot": True, "reason": "try to use synthetic data as a pilot"},
    )
    assert tagged.status_code == 404
    pilot = client.post(
        f"{BASE}/pilot-variance",
        json={
            "design": "within-subjects",
            "test": "paired-t",
            "counterbalanced": True,
            "measure_id": "first-green-time",
        },
    )
    assert pilot.status_code == 422


def test_data_tab_reads_return_the_labelled_example_sessions(client):
    status = client.get(f"{BASE}/status?includeSynthetic=true").json()
    assert status["syntheticExample"] is True
    sessions = status["sessions"]
    assert len(sessions) == SESSIONS
    by_condition = Counter(s["condition"] for s in sessions)
    assert set(by_condition) == set(CONDITIONS)
    assert min(by_condition.values()) >= COMPLETED_PARTICIPANTS

    # The imperfect sessions the integrity UI exists for.
    incomplete = [s for s in sessions if not s["complete"]]
    assert {s["sessionId"] for s in incomplete} == {
        "example-synthetic-P07-2",
        f"example-synthetic-P{COMPLETED_PARTICIPANTS + 1:02d}-1",
    }
    assert {s["missingEvents"] for s in incomplete} == {1, 2}
    flagged = [s for s in sessions if s["flaggedEvents"]]
    assert [s["flagKinds"] for s in flagged] == [["task-mismatch"]]

    rows = client.get(f"{BASE}/dataset?includeSynthetic=true").json()["rows"]
    assert all(r["payload"]["synthetic"] is True for r in rows)
    green: dict[tuple, int] = {}
    for r in rows:
        if r["type"] == "task_outcome" and r["payload"].get("firstGreenMs"):
            assert r["source"] == "task-harness"
            green[(r["participantId"], r["condition"])] = r["payload"]["firstGreenMs"]
    assert len(green) == COMPLETED_PARTICIPANTS * 2
    assert all(7 * 60_000 <= ms <= 41 * 60_000 for ms in green.values())
    without, with_tool = (
        [ms for (_, c), ms in green.items() if c == condition]
        for condition in CONDITIONS
    )
    assert len(without) == len(with_tool) == COMPLETED_PARTICIPANTS
    assert sum(with_tool) < sum(without)

    protocol = client.get(f"{BASE}/protocol").json()["document"]
    survey = protocol["instruments"]["surveys"][0]
    answers = [r for r in rows if r["type"] == "survey_response"]
    assert len(answers) == COMPLETED_PARTICIPANTS * 2
    assert all(validated_responses(survey, r["payload"]["responses"]) for r in answers)
    assert {r["type"] for r in rows} >= {
        "session_start",
        "environment_snapshot",
        "edit_burst",
        "ai_suggestion",
        "fatigue_response",
        "session_end",
    }

    audit = client.get(f"{BASE}/control-arm-audit?includeSynthetic=true").json()
    assert {s["condition"] for s in audit["sessions"]} == {CONDITIONS[0]}
    statuses = Counter(s["status"] for s in audit["sessions"])
    assert statuses["evidence-of-ai-use"] == 1
    assert statuses["cannot-assess"] == 1
    assert statuses["no-evidence"] == len(audit["sessions"]) - 2 >= 10

    events = client.get(f"/sessions/{sessions[0]['sessionId']}/events").json()
    assert events and events[0]["type"] == "session_start"


def test_no_other_study_is_marked_as_the_synthetic_example(client):
    document = client.get(f"{BASE}/protocol").json()["document"]
    other = client.post(
        "/projects/implicit/studies",
        json={"name": "A real study", "protocol": document},
    ).json()["id"]
    assert other != EXAMPLE_STUDY_ID
    status = client.get(f"/studies/{other}/status").json()
    assert status["syntheticExample"] is False
    assert status["sessions"] == []
    assert (
        client.get(f"/studies/{other}/status?includeSynthetic=true").json()["sessions"]
        == []
    )


def test_example_links_are_illustrative_and_do_not_expose_connection_strings(client):
    links = client.get(f"{BASE}/enrollment/tokens").json()
    assert len(links) == PLANNED_PARTICIPANTS
    assert all(link["illustrative"] is True for link in links)
    assert all(link["connectionString"] is None for link in links)
    assert all(link["captureConfig"] for link in links)


def test_example_cannot_mint_live_capture_links(client, seeded):
    before = _counts(seeded)
    response = client.post(f"{BASE}/enrollment/tokens", json={"count": 1})
    assert response.status_code == 409
    assert "illustrative" in response.json()["detail"]
    assert "separate study" in response.json()["detail"]
    assert _counts(seeded) == before


@pytest.mark.parametrize("redeemed", [True, False])
@pytest.mark.parametrize("expired", [True, False])
def test_example_tokens_refuse_live_pairing_before_expiry_checks(
    client, seeded, redeemed, expired
):
    with make_session_factory(seeded.db_url)() as s:
        row = s.scalar(
            select(EnrollmentToken).where(
                EnrollmentToken.redeemed_at.is_not(None)
                if redeemed
                else EnrollmentToken.redeemed_at.is_(None)
            )
        )
        token = row.token
        row.expires_at = (
            "2000-01-01T00:00:00+00:00" if expired else "2099-01-01T00:00:00+00:00"
        )
        s.commit()
    before = _counts(seeded)
    response = client.post(
        "/pair/redeem?seeding_example=true",
        json={"token": token, "seeding_example": True},
        headers={"X-Seeding-Example": "true"},
    )
    assert response.status_code == 409
    assert "illustrative" in response.json()["detail"]
    assert "separate study" in response.json()["detail"]
    assert _counts(seeded) == before


def test_a_separate_study_still_mints_and_redeems_live_links(client):
    document = client.get(f"{BASE}/protocol").json()["document"]
    study = client.post(
        "/projects/implicit/studies",
        json={"name": "A live capture rehearsal", "protocol": document},
    ).json()["id"]
    response = client.post(f"/studies/{study}/enrollment/tokens", json={"count": 1})
    assert response.status_code == 200, response.text
    link = response.json()[0]
    assert isinstance(link["connectionString"], str)
    listed = client.get(f"/studies/{study}/enrollment/tokens").json()[0]
    assert "illustrative" not in listed
    assert listed["connectionString"] == link["connectionString"]
    response = client.post(
        "/pair/redeem",
        json={"token": link["connectionString"].rsplit("#", 1)[-1]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["studyId"] == study
