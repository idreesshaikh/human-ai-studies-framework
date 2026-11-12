import copy
import io
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest
from analysis.adherence_sim import MIXES, Scenario, mixed_sensitivity, simulate
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

from analysis import calibration_rates
from middleware import planner_routes

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


def _study_with_non_control_session(client):
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
    template = next(e for e in _pilot_events() if e["condition"] == "tool-version-b")
    capture = {"aiLifecycle": True, "editBursts": True, "clipboard": True}
    # A complete capture: boundaries, full audit coverage and contiguous seq.
    events = [
        {**template, "seq": seq, "type": kind, "payload": payload}
        for seq, (kind, payload) in enumerate(
            [
                ("session_start", {}),
                ("environment_snapshot", {"auditCapture": capture}),
                ("ai_suggestion", {"action": "accepted"}),
                ("session_end", {}),
            ]
        )
    ]
    assert client.post("/ingest/events", json=events).status_code == 200
    return template["sessionId"]


def test_calibration_endpoint_accepts_non_control_session(client):
    session = _study_with_non_control_session(client)
    body = {
        "labels": {session: True},
        "scenarios": {session: "copilot-inline"},
        "source": "Independent scripted-session observer fixture; "
        "not a real calibration result",
    }
    result = client.post(f"/studies/{STUDY}/audit-calibration", json=body)
    assert result.status_code == 200, result.text
    by_scenario = result.json()["byScenario"]["copilot-inline"]
    assert by_scenario["labelled"] == 1
    assert by_scenario["assessed"] == 1
    assert by_scenario["incompleteCaptureExcluded"] == 0
    signal = by_scenario["signals"]["accepted_inline_suggestion"]
    assert signal["fired"]["value"] == 1
    assert signal["sensitivity"]["value"] == 1
    audit = client.get(f"/studies/{STUDY}/control-arm-audit").json()
    assert audit["sessions"] == []
    assert audit["records"][0]["record"]["scenarios"] == {session: "copilot-inline"}


def test_calibration_endpoint_rejects_scenario_without_label(client):
    session = _study_with_non_control_session(client)
    body = {
        "labels": {session: True},
        "scenarios": {session: "copilot-inline", "unlabelled": "retype"},
        "source": "Independent scripted-session observer fixture",
    }
    result = client.post(f"/studies/{STUDY}/audit-calibration", json=body)
    assert result.status_code == 422
    assert "labelled session" in result.text
    body["scenarios"].pop("unlabelled")
    retry = client.post(f"/studies/{STUDY}/audit-calibration", json=body)
    assert retry.status_code == 200, retry.text


def test_get_plan_returns_ai_access_warnings(client):
    body = client.get(f"/studies/{STUDY}/plan").json()
    assert isinstance(body["aiAccessWarnings"], list)
    assert body["aiAccessWarnings"] == []


def test_get_plan_ai_access_warnings_flag_an_undeclared_policy(client):
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
    warnings = client.get(f"/studies/{STUDY}/plan").json()["aiAccessWarnings"]
    assert [w["code"] for w in warnings] == ["ai-access-undeclared"]


def test_get_plan_survives_a_malformed_ai_access_draft(client):
    import yaml

    protocol = load_protocol(EXAMPLE)
    protocol["controlConditions"] = ["tool-version-a"]
    protocol["aiAccess"] = {
        "conditions": {"tool-version-a": "garbage", "ghost": ["x"]},
        "deviationStrategy": 3,
    }
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
    response = client.get(f"/studies/{STUDY}/plan")
    assert response.status_code == 200, response.text
    assert response.json()["aiAccessWarnings"] == []


NONCOMPLIANCE_URL = f"/studies/{STUDY}/plan/noncompliance"
NO_CALIBRATION = (
    "Calibration rates are not available yet; "
    "enter sensitivity and specificity instead."
)


def noncompliance_body(**extra):
    return {
        "effect_d": 0.5,
        "n_per_arm": 30,
        "control_violation": 0.25,
        "treatment_nonuse": 0.1,
        "mechanism": "random",
        "sensitivity": 0.8,
        "specificity": 0.95,
        **extra,
    }


@pytest.fixture
def fast_noncompliance(monkeypatch):
    """Small replicate counts for speed, and no calibration unless a test adds it."""
    monkeypatch.setattr(planner_routes, "NONCOMPLIANCE_REPS", 60)
    monkeypatch.setattr(planner_routes, "NONCOMPLIANCE_REQUIRED_N_REPS", 40)
    monkeypatch.setattr(calibration_rates, "PER_ROUTE", None)
    monkeypatch.setattr(calibration_rates, "SPECIFICITY", None)


@pytest.fixture
def calibrated(fast_noncompliance, monkeypatch):
    per_route = dict.fromkeys(MIXES["instruction-only"], 0.9)
    per_route["retype"] = 0.2
    monkeypatch.setattr(calibration_rates, "PER_ROUTE", per_route)
    monkeypatch.setattr(calibration_rates, "SPECIFICITY", 0.97)
    return per_route


def test_noncompliance_entered_rates_returns_estimators(client, fast_noncompliance):
    response = client.post(NONCOMPLIANCE_URL, json=noncompliance_body())
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body["estimators"]) == {"itt", "exclude-detected", "as-detected"}
    for metrics in body["estimators"].values():
        assert set(metrics) == {"bias", "coverage", "power", "refused"}
    assert set(body["requiredN"]) == {"itt", "exclude-detected"}
    assert body["detection"] == {
        "sensitivity": 0.8,
        "specificity": 0.95,
        "source": "entered",
    }
    # The route uses the fixed seed, so it matches a direct simulation.
    scenario = Scenario(0.5, 30, 0.25, 0.1, "random", 0.8, 0.95)
    assert body["estimators"] == simulate(scenario, reps=60)


def test_noncompliance_mix_without_calibration_is_422(client, fast_noncompliance):
    body = noncompliance_body(mix="instruction-only")
    del body["sensitivity"], body["specificity"]
    response = client.post(NONCOMPLIANCE_URL, json=body)
    assert response.status_code == 422
    assert response.json()["detail"] == NO_CALIBRATION


def test_noncompliance_mix_with_missing_specificity_calibration_is_422(
    client, calibrated, monkeypatch
):
    monkeypatch.setattr(calibration_rates, "SPECIFICITY", None)
    body = noncompliance_body(mix="locked-environment")
    del body["sensitivity"], body["specificity"]
    response = client.post(NONCOMPLIANCE_URL, json=body)
    assert response.status_code == 422
    assert response.json()["detail"] == NO_CALIBRATION


def test_noncompliance_rejects_both_mix_and_sensitivity(client, fast_noncompliance):
    response = client.post(
        NONCOMPLIANCE_URL, json=noncompliance_body(mix="instruction-only")
    )
    assert response.status_code == 422
    assert "either" in response.json()["detail"]


def test_noncompliance_requires_a_detection_source(client, fast_noncompliance):
    body = noncompliance_body()
    del body["sensitivity"], body["specificity"]
    response = client.post(NONCOMPLIANCE_URL, json=body)
    assert response.status_code == 422
    assert "mix or a sensitivity" in response.json()["detail"]


def test_noncompliance_entered_sensitivity_needs_specificity(
    client, fast_noncompliance
):
    body = noncompliance_body()
    del body["specificity"]
    response = client.post(NONCOMPLIANCE_URL, json=body)
    assert response.status_code == 422
    assert "specificity" in response.json()["detail"]


def test_noncompliance_mix_uses_calibrated_rates(client, calibrated):
    body = noncompliance_body(mix="locked-environment")
    del body["sensitivity"], body["specificity"]
    response = client.post(NONCOMPLIANCE_URL, json=body)
    assert response.status_code == 200, response.text
    detection = response.json()["detection"]
    assert detection["source"] == "calibration"
    assert detection["specificity"] == 0.97
    assert detection["sensitivity"] == pytest.approx(
        mixed_sensitivity(calibrated, MIXES["locked-environment"])
    )
    assert detection["sensitivity"] == pytest.approx(0.55)


def test_noncompliance_calibrated_mix_refuses_a_specificity_override(
    client, calibrated
):
    body = noncompliance_body(mix="instruction-only")
    del body["sensitivity"]
    response = client.post(NONCOMPLIANCE_URL, json=body)
    assert response.status_code == 422
    assert "calibrated specificity" in response.json()["detail"]


def test_noncompliance_unknown_mix_is_422(client, calibrated):
    body = noncompliance_body(mix="telepathy")
    del body["sensitivity"], body["specificity"]
    response = client.post(NONCOMPLIANCE_URL, json=body)
    assert response.status_code == 422
    assert "telepathy" in response.json()["detail"]


def test_noncompliance_mix_naming_an_uncalibrated_route_is_422(
    client, calibrated, monkeypatch
):
    monkeypatch.setattr(calibration_rates, "PER_ROUTE", {"retype": 0.2})
    body = noncompliance_body(mix="instruction-only")
    del body["sensitivity"], body["specificity"]
    response = client.post(NONCOMPLIANCE_URL, json=body)
    assert response.status_code == 422
    assert "without a sensitivity" in response.json()["detail"]


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        ({"n_per_arm": 1001}, "n_per_arm"),
        ({"effect_d": 11}, "effect_d"),
        ({"effect_d": -11}, "effect_d"),
        ({"n_per_arm": 3}, "n_per_arm"),
        ({"control_violation": 0.6}, "control_violation"),
        ({"treatment_nonuse": 1.5}, "treatment_nonuse"),
        ({"sensitivity": -0.1}, "sensitivity"),
        ({"specificity": 2}, "specificity"),
        ({"mechanism": "telepathy"}, "mechanism"),
    ],
)
def test_noncompliance_invalid_scenario_is_422_with_a_message(
    client, fast_noncompliance, change, fragment
):
    response = client.post(NONCOMPLIANCE_URL, json=noncompliance_body(**change))
    assert response.status_code == 422, response.text
    assert fragment in response.json()["detail"]


@pytest.mark.parametrize("change", [{"effect_d": None}, {"unexpected": 1}])
def test_noncompliance_rejects_malformed_bodies(client, fast_noncompliance, change):
    response = client.post(NONCOMPLIANCE_URL, json=noncompliance_body(**change))
    assert response.status_code == 422


def test_noncompliance_edge_rates_return_numbers_or_a_refusal(
    client, fast_noncompliance
):
    response = client.post(
        NONCOMPLIANCE_URL,
        json=noncompliance_body(
            control_violation=0.35, treatment_nonuse=1, sensitivity=0, specificity=1
        ),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # Nobody is ever flagged, so the as-detected comparison has no second group.
    assert body["estimators"]["as-detected"] == {
        "bias": None,
        "coverage": None,
        "power": None,
        "refused": 60,
    }
    assert body["estimators"]["itt"]["refused"] == 0
    assert set(body["requiredN"]) == {"itt", "exclude-detected"}


def test_noncompliance_required_n_is_none_when_the_target_is_out_of_reach(
    client, fast_noncompliance
):
    response = client.post(
        NONCOMPLIANCE_URL, json=noncompliance_body(effect_d=0, n_per_arm=10)
    )
    assert response.status_code == 200, response.text
    assert response.json()["requiredN"] == {"itt": None, "exclude-detected": None}
