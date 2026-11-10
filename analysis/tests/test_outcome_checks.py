from copy import deepcopy

import pytest
from analysis.outcome_checks import check_outcome_capture
from protocol.measures import shipped_instruments
from protocol.versioning import version_record


@pytest.fixture
def protocol():
    survey = next(i for i in shipped_instruments() if i["id"] == "raw-nasa-tlx")
    return {
        "protocolVersion": 6,
        "study": {"id": "example"},
        "conditions": ["control", "assisted"],
        "participants": {"design": "within-subjects"},
        "tasks": [{"id": "bug"}],
        "instruments": {
            "tern": {},
            "taskHarness": {"enabled": True},
            "surveys": [survey],
        },
        "measures": [
            {
                "id": "first-green",
                "construct": "Time to first green",
                "instrument": "taskHarness",
                "fields": ["task_outcome.firstGreenMs"],
                "analysisRecipe": "paired-nonparametric",
            }
        ],
    }


def event(
    condition="control",
    *,
    participant="P1",
    source="task-harness",
    kind="task_outcome",
    seq=0,
    **payload,
):
    return {
        "sessionId": f"{participant}-{condition}",
        "participantId": participant,
        "condition": condition,
        "taskId": "bug",
        "source": source,
        "seq": seq,
        "schemaVersion": 4,
        "type": kind,
        "flags": [],
        "payload": {
            "passed": True,
            "total": 3,
            "failed": 0,
            "firstGreenMs": 1000,
            **payload,
        },
    }


def outcome(protocol, rows, **kwargs):
    return check_outcome_capture(protocol, rows, **kwargs)["outcomes"][0]


def codes(result):
    return {issue["code"] for issue in result["issues"]}


def test_observed_pairs_and_traceability_do_not_change_records(protocol):
    rows = [event(), event("assisted")]
    rows[0]["pilot"] = True
    before = deepcopy((protocol, rows))
    report = check_outcome_capture(protocol, rows)
    result = report["outcomes"][0]
    assert result["status"] == "observed"
    assert result["pairedParticipants"] == 1
    assert result["participantsByCondition"] == {"control": 1, "assisted": 1}
    assert result["evidence"][0] == {
        "sessionId": "P1-assisted",
        "source": "task-harness",
        "seq": 0,
        "schemaVersion": 4,
    }
    assert (protocol, rows) == before
    assert report == check_outcome_capture(protocol, rows)
    assert len(report["protocolHash"]) == len(report["dataHash"]) == 64
    assert "payload" not in str(result["evidence"])
    rows[0]["payload"]["firstGreenMs"] += 1
    assert report["dataHash"] != check_outcome_capture(protocol, rows)["dataHash"]


@pytest.mark.parametrize(
    "value", [None, "1000", True, -1, float("nan"), float("inf"), 10**1000]
)
def test_bad_times_are_not_observed(protocol, value):
    result = outcome(protocol, [event(firstGreenMs=value)])
    assert result["observedUnits"] == 0
    assert "first-green" in codes(result)


def test_disabled_producer_and_custom_contract_abstention(protocol):
    protocol["instruments"]["taskHarness"]["enabled"] = False
    result = outcome(protocol, [event()])
    assert result["status"] == "configuration" and result["observedUnits"] == 0
    protocol["measures"][0]["fields"] = ["task_outcome.firstGreenSeconds"]
    result = outcome(protocol, [event(firstGreenSeconds=1)])
    assert result["status"] == "unverified" and result["observedUnits"] is None
    protocol["measures"] = ["Productivity"]
    assert outcome(protocol, [])["status"] == "unverified"


def test_no_data_is_distinct_from_missing_inputs(protocol):
    assert outcome(protocol, [])["status"] == "not-observed"
    assert (
        outcome(protocol, [event(source="tern", kind="session_start")])["status"]
        == "missing"
    )
    protocol["measures"] = []
    assert check_outcome_capture(protocol, [])["outcomes"] == []


def test_current_event_schema_is_supported_and_source_identity_matters(protocol):
    row = event()
    row["schemaVersion"] = 6
    assert outcome(protocol, [row])["observedUnits"] == 1
    row["source"] = "agent-capture"
    assert outcome(protocol, [row])["observedUnits"] == 0


def test_failure_is_noncompletion_not_zero_or_a_fake_passing_test(protocol):
    failed = event(passed=False, failed=1)
    failed["payload"].pop("firstGreenMs")
    result = outcome(protocol, [failed])
    assert result["observedUnits"] == 0 and "no-passing-run" in codes(result)
    assert "no-passing-run" not in codes(outcome(protocol, [failed, event(seq=1)]))
    assert "test-result" in codes(outcome(protocol, [event(total=0)]))
    protocol["measures"][0].update(
        fields=["task_outcome.passed"], analysisRecipe="two-proportion"
    )
    assert outcome(protocol, [failed])["status"] == "unverified"
    protocol["participants"]["design"] = "between-subjects"
    assert outcome(protocol, [failed])["observedUnits"] == 1


@pytest.mark.parametrize(
    "mutate,code",
    [
        (lambda r: r.update(seq=10**12), "sequence"),
        (lambda r: r.update(seq=True), "sequence"),
        (lambda r: r.update(taskId="other"), "identity"),
        (lambda r: r.update(condition="unknown"), "identity"),
        (lambda r: r.update(sessionId=""), "identity"),
        (lambda r: r.update(participantId=""), "identity"),
        (lambda r: r.update(flags=["task-mismatch"]), "integrity"),
        (lambda r: r.update(inclusionDecision="exclude"), "excluded"),
        (lambda r: r.update(schemaVersion=999), "schema"),
    ],
)
def test_invalid_attribution_and_integrity_do_not_count(protocol, mutate, code):
    row = event()
    mutate(row)
    result = outcome(protocol, [row])
    assert result["observedUnits"] == 0 and code in codes(result)


def test_conflicting_identity_duplicates_and_incomplete_pairs(protocol):
    row = event()
    conflicting = {**event(seq=1), "participantId": "P2"}
    assert "identity" in codes(outcome(protocol, [row, conflicting]))
    assert "sequence" in codes(outcome(protocol, [row, row]))
    result = outcome(protocol, [row, event("assisted", participant="P2")])
    assert result["observedUnits"] == 2 and result["pairedParticipants"] == 0
    assert result["status"] == "review" and "pair-coverage" in codes(result)
    protocol["participants"]["design"] = "between-subjects"
    protocol["measures"][0]["analysisRecipe"] = "two-group-nonparametric"
    assert "independence" in codes(outcome(protocol, [row, event("assisted")]))


def test_synthetic_session_is_excluded_wholly_and_only_opted_in_explicitly(protocol):
    rows = [
        event(),
        event("assisted", synthetic=True),
        event("assisted", seq=1, kind="session_end"),
    ]
    report = check_outcome_capture(protocol, rows)
    assert report["sessionUnits"] == 1 and report["synthetic"] is False
    example = check_outcome_capture(protocol, rows, include_synthetic=True)
    assert example["sessionUnits"] == 2 and example["synthetic"] is True
    assert example["outcomes"][0]["pairedParticipants"] == 1


def survey_event(protocol, **payload):
    survey = protocol["instruments"]["surveys"][0]
    return event(
        source="tern",
        kind="survey_response",
        instrumentId=survey["id"],
        instrumentVersion=survey["version"],
        instrumentHash=version_record(survey)["sha256"],
        responses={i["id"]: 50 for i in survey["items"]},
        **payload,
    )


def test_survey_scores_are_recomputed_and_versioned(protocol):
    survey = protocol["instruments"]["surveys"][0]
    protocol["measures"] = [
        {
            "id": "workload",
            "construct": "Workload",
            "instrument": survey["id"],
            "fields": ["survey_response.score"],
            "analysisRecipe": "typed-measures",
        }
    ]
    row = survey_event(protocol, score="untrusted-client-score")
    assert outcome(protocol, [row])["observedUnits"] == 1
    for key, value, expected in [
        ("instrumentVersion", "wrong", "survey-version"),
        ("instrumentHash", "wrong", "survey-version"),
        ("responses", {}, "survey-response"),
        ("responses", {i["id"]: True for i in survey["items"]}, "survey-response"),
        ("responses", {i["id"]: 51 for i in survey["items"]}, "survey-response"),
        ("responses", {i["id"]: 10**1000 for i in survey["items"]}, "survey-response"),
    ]:
        bad = deepcopy(row)
        bad["payload"][key] = value
        result = outcome(protocol, [bad])
        assert result["observedUnits"] == 0 and expected in codes(result)
    survey["scoring"] = "none"
    assert outcome(protocol, [row])["status"] == "unverified"


def test_issue_samples_are_bounded_and_recipe_checks_abstain(protocol):
    rows = [event(participant=f"P{i}", firstGreenMs=None) for i in range(30)]
    issue = outcome(protocol, rows)["issues"][0]
    assert issue["units"] == 30 and len(issue["sessionIds"]) == 5
    protocol["measures"][0]["analysisRecipe"] = "custom"
    assert outcome(protocol, rows)["status"] == "unverified"


def test_baseline_covariates_do_not_get_repeated_outcome_warnings(protocol):
    survey = protocol["instruments"]["surveys"][0]
    survey["timing"] = "pre-task"
    protocol["measures"] = [
        {
            "id": "baseline",
            "construct": "Baseline response",
            "instrument": survey["id"],
            "fields": ["pre_task_covariate.responses.mental_demand"],
            "analysisRecipe": "typed-measures",
        }
    ]
    row = survey_event(protocol)
    row["type"] = "pre_task_covariate"
    result = outcome(protocol, [row])
    assert result["status"] == "unverified"
    assert codes(result) == {"unverified-contract"}
    assert "Baseline" in result["issues"][0]["message"]


def test_editing_a_report_does_not_change_inputs_or_later_reports(protocol):
    report = check_outcome_capture(protocol, [event()])
    original = deepcopy(report)
    report["outcomes"][0]["fields"].append("changed")
    report["limitations"].clear()
    assert check_outcome_capture(protocol, [event()]) == original
