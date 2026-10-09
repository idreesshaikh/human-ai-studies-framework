import copy
import io
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest
from analysis.dataset import Dataset
from analysis.recipes.typed_measures import run as score_measures
from analysis.runner import run_plan
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.db import ProtocolDraftRow, SessionOpen, StudyPlan, make_session_factory
from middleware.enrollment import build_capture_config
from middleware.settings import Settings
from protocol.loader import load_protocol
from protocol.versioning import content_hash

ROOT = Path(__file__).parents[2]
EXAMPLE = ROOT / "protocol/examples/planner-v6.yaml"
STUDY = "planner-example"


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        db_path=tmp_path / "planner.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=EXAMPLE,
        spa_dist=tmp_path / "missing",
    )
    client = TestClient(create_app(settings))
    client.db_path = settings.db_path
    return client


def assumptions(**extra):
    return {
        "design": "within-subjects",
        "test": "wilcoxon",
        "counterbalanced": True,
        "effect": 0.5,
        "sd": 1,
        "max_n": 120,
        "simulations": 200,
        "measure_id": "completion-time",
        **extra,
    }


def test_saved_plan_pins_protocol_hash_and_stale_state(client):
    response = client.post(f"/studies/{STUDY}/plan", json=assumptions())
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["basis"] == "assumptions"
    assert plan["protocol"]["protocolVersion"] == 6
    assert plan["protocol"]["protocolHash"] == content_hash(load_protocol(EXAMPLE))
    with make_session_factory(f"sqlite:///{client.db_path}")() as s:
        record = s.get(StudyPlan, plan["planId"])
        assert record.inputs["measure_id"] == "completion-time"
        changed = copy.deepcopy(record.protocol)
        changed["participants"]["planned"] = 48
        import yaml

        s.add(
            ProtocolDraftRow(
                study_id=STUDY,
                yaml=yaml.safe_dump(changed),
                compilation_id="",
                updated_at="",
            )
        )
        s.commit()
    loaded = client.get(f"/studies/{STUDY}/plan").json()
    assert loaded["plan"]["stale"]
    assert (
        loaded["plan"]["protocol"]["protocolHash"] == plan["protocol"]["protocolHash"]
    )


@pytest.mark.parametrize(
    "change",
    [
        {"test": "paired-t"},
        {"design": "crossover"},
        {"measure_id": "missing"},
        {"measure_id": None},
        {"covariate_correlation": 0.5},
    ],
)
def test_request_must_match_recorded_measure_test_design(client, change):
    response = client.post(f"/studies/{STUDY}/plan", json=assumptions(**change))
    assert response.status_code == 422, response.text
    assert client.get(f"/studies/{STUDY}/plan").json()["plan"] is None


def test_every_instrument_round_trips_through_extension_ingest_and_recipe(
    client,
):
    proto = load_protocol(EXAMPLE)
    config = build_capture_config(proto, "P01", proto["conditions"][0])
    proc = subprocess.run(
        [
            shutil.which("node"),
            "--experimental-strip-types",
            str(ROOT / "extension/test/surveyBridge.mjs"),
        ],
        input=json.dumps(config),
        capture_output=True,
        text=True,
        check=True,
    )
    events = json.loads(proc.stdout)
    assert len(events) == 4
    response = client.post("/ingest/events", json={"source": "tern", "events": events})
    assert response.status_code == 200, response.text
    assert response.json()["flagged"] == 0
    rows = client.get(f"/studies/{STUDY}/dataset").json()["rows"]
    result = score_measures(Dataset(rows, meta={"protocol": proto}))
    scores = result.tables["scores"]
    assert len(scores) == 8  # six legacy items + raw TLX + SUS
    assert scores.loc[scores.measureId == "sus-1", "value"].iloc[0] == 100
    assert scores.loc[scores.measureId == "raw-nasa-tlx-1", "value"].iloc[0] == 100
    # The skill form is captured separately, not treated as an outcome.
    assert any(r["type"] == "pre_task_covariate" for r in rows)
    changed = copy.deepcopy(rows)
    for row in changed:
        row["payload"]["instrumentVersion"] = "unexpected"
    assert (
        score_measures(Dataset(changed, meta={"protocol": proto}))
        .tables["scores"]
        .empty
    )


def _pilot_events():
    events = []
    for i in range(8):
        for j, condition in enumerate(("tool-version-a", "tool-version-b")):
            events.append(
                {
                    "v": 6,
                    "seq": 0,
                    "ts": "2026-10-08T10:00:00Z",
                    "mono": 0,
                    "sessionId": f"pilot-{i}-{j}",
                    "participantId": f"P{i + 1:02d}",
                    "condition": condition,
                    "type": "task_outcome",
                    "payload": {"firstGreenMs": 100 + i * 2 if j == 0 else 110 + i * 3},
                }
            )
    return events


def test_pilot_update_requires_tags_ignores_synthetic_and_excludes_confirmatory_rows(
    client, tmp_path
):
    events = _pilot_events()
    assert client.post("/ingest/events", json=events).status_code == 200
    assert (
        client.post(
            f"/studies/{STUDY}/pilot-variance", json=assumptions(effect=2)
        ).status_code
        == 422
    )
    for event in events:
        response = client.post(
            f"/studies/{STUDY}/sessions/{event['sessionId']}/annotation",
            json={"pilot": True, "reason": "Pilot recruitment cohort"},
        )
        assert response.status_code == 200, response.text
    updated = client.post(
        f"/studies/{STUDY}/pilot-variance", json=assumptions(effect=2)
    )
    assert updated.status_code == 200, updated.text
    plan = updated.json()
    assert plan["basis"] == "pilot-data" and plan["pilot"]["participants"] == 8
    assert plan["pilot"]["actionable"] and plan["before"]["basis"] == "assumptions"
    assert len(plan["pilotSensitivity"]) == 2
    rows = client.get(f"/studies/{STUDY}/dataset").json()["rows"]
    assert all(r["pilot"] for r in rows)
    assert Dataset(rows).events.empty
    result = run_plan(
        load_protocol(EXAMPLE), Dataset(rows), STUDY, out_root=tmp_path / "report"
    )
    assert "paired-nonparametric" not in result.executed
    synthetic = {
        **events[0],
        "sessionId": "synthetic",
        "payload": {"firstGreenMs": 99999999, "synthetic": True},
    }
    client.post("/ingest/events", json=[synthetic])
    assert (
        client.post(
            f"/studies/{STUDY}/sessions/synthetic/annotation",
            json={"pilot": True, "reason": "must not work"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/studies/{STUDY}/pilot-variance", json=assumptions(effect=2)
        ).json()["pilot"]["sd"]
        == plan["pilot"]["sd"]
    )
    archive = zipfile.ZipFile(
        io.BytesIO(client.get(f"/studies/{STUDY}/data-bundle").content)
    )
    card = json.loads(archive.read("design-card.json"))
    assert card["plannedPower"]["basis"] == "pilot-data"
    assert len(card["inclusionDecisions"]) == 16
    assert "design-card.md" in archive.namelist()


def test_session_annotation_cannot_cross_study_scope(client):
    client.post("/ingest/events", json=_pilot_events())
    with make_session_factory(f"sqlite:///{client.db_path}")() as s:
        s.add(
            SessionOpen(
                session_id="other-session",
                study_id="other",
                protocol_version=6,
                opened_at="",
            )
        )
        s.commit()
    event = {**_pilot_events()[0], "sessionId": "other-session"}
    client.post("/ingest/events", json=[event])
    response = client.post(
        f"/studies/{STUDY}/sessions/other-session/annotation",
        json={"pilot": True, "reason": "must not work"},
    )
    assert response.status_code == 404


def test_independent_calibration_and_inclusion_history_are_recorded(client):
    import yaml

    protocol = load_protocol(EXAMPLE)
    protocol["controlConditions"] = ["tool-version-a"]
    with make_session_factory(f"sqlite:///{client.db_path}")() as s:
        s.add(
            ProtocolDraftRow(
                study_id=STUDY,
                yaml=yaml.safe_dump(protocol),
                compilation_id="",
                updated_at="",
            )
        )
        s.commit()
    events = _pilot_events()[:2]
    positive = events[0]["sessionId"]
    events += [
        {
            **events[0],
            "seq": 1,
            "type": "ai_suggestion",
            "payload": {"action": "accepted"},
        }
    ]
    assert client.post("/ingest/events", json=events).status_code == 200
    body = {
        "labels": {positive: True},
        "source": "Independent scripted-session observer fixture; "
        "not a real calibration result",
    }
    result = client.post(f"/studies/{STUDY}/audit-calibration", json=body)
    assert result.status_code == 200, result.text
    assert result.json()["signals"]["combined"]["sensitivity"]["value"] == 1
    assert result.json()["signals"]["combined"]["specificity"]["value"] is None
    for decision in ("include", "exclude"):
        assert (
            client.post(
                f"/studies/{STUDY}/sessions/{positive}/annotation",
                json={
                    "decision": decision,
                    "reason": f"Researcher fixture decision: {decision}",
                },
            ).status_code
            == 200
        )
    audit = client.get(f"/studies/{STUDY}/control-arm-audit").json()
    assert audit["sessions"][0]["decision"]["decision"] == "exclude"
    assert [r["kind"] for r in audit["records"]] == [
        "calibration",
        "session-decision",
        "session-decision",
    ]
    card = client.get(f"/studies/{STUDY}/design-card").json()
    assert len(card["audit"]["records"]) == 3
    assert card["audit"]["records"][0]["record"]["source"] == body["source"]
    assert (
        client.post(
            f"/studies/{STUDY}/audit-calibration",
            json={"labels": {"private-other-session": True}, "source": "invalid"},
        ).status_code
        == 422
    )
