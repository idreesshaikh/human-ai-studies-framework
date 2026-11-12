"""The optional ``aiAccess`` section: per-condition AI policy and verification."""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from middleware.example_study import example_protocol
from protocol.ai_access import UNVERIFIED_ROUTES, ai_access_warnings
from protocol.loader import validate_protocol

from protocol import ai_access as ai_access_module

_EXAMPLES = sorted((Path(__file__).parents[1] / "examples").glob("*.yaml"))

# evidence-map.yaml is an evidence map, not a study protocol. It already failed
# validation before aiAccess existed (ruling R3: report, do not fix).
_NOT_A_PROTOCOL = {
    "evidence-map.yaml": (
        "pre-existing: not a study protocol; schema reports 'protocolVersion', "
        "'study', 'researchQuestions', 'conditions', 'participants', 'session', "
        "'instruments', 'phases', 'analysisPlan' as required properties and "
        "'description', 'mapId', 'mapVersion', 'publications', 'relations', "
        "'schemaVersion', 'studies' as additional properties"
    ),
}


def _example_params() -> list:
    params = []
    for path in _EXAMPLES:
        marks = ()
        if path.name in _NOT_A_PROTOCOL:
            marks = (pytest.mark.xfail(strict=True, reason=_NOT_A_PROTOCOL[path.name]),)
        params.append(pytest.param(path, id=path.name, marks=marks))
    return params


def _ai_access(protocol: dict) -> dict:
    return {
        "conditions": {
            protocol["conditions"][0]: {
                "aiAllowed": False,
                "enforcement": ["instruction"],
                "verification": ["self-report", "ide-telemetry"],
            },
            protocol["conditions"][1]: {
                "aiAllowed": True,
                "allowedTools": ["GitHub Copilot"],
                "enforcement": ["none"],
                "verification": ["agent-hooks"],
            },
        },
        "deviationStrategy": "itt",
        "sensitivityAnalysis": True,
    }


@pytest.fixture
def protocol() -> dict:
    return deepcopy(example_protocol())


@pytest.mark.parametrize("path", _example_params())
def test_every_bundled_example_still_validates(path):
    assert validate_protocol(yaml.safe_load(path.read_text("utf-8"))) == []


def test_ai_access_section_validates(protocol):
    protocol["aiAccess"] = _ai_access(protocol)
    assert validate_protocol(protocol) == []


def test_ai_access_unknown_condition_is_error(protocol):
    protocol["aiAccess"] = _ai_access(protocol)
    protocol["aiAccess"]["conditions"]["ghost"] = {
        "aiAllowed": False,
        "enforcement": ["none"],
        "verification": ["none"],
    }
    assert validate_protocol(protocol) == [
        "aiAccess.conditions.ghost: not a declared condition"
    ]


def test_ai_access_bad_enforcement_is_error(protocol):
    protocol["aiAccess"] = _ai_access(protocol)
    first = protocol["conditions"][0]
    protocol["aiAccess"]["conditions"][first]["enforcement"] = ["honour-system"]
    errors = validate_protocol(protocol)
    assert errors != []
    assert all(
        e.startswith(f"aiAccess.conditions.{first}.enforcement.0:") for e in errors
    )


def _locked_itt(protocol: dict) -> dict:
    """A protocol whose control condition is locked down and analysed by ITT."""
    control, treatment = protocol["conditions"][:2]
    protocol["controlConditions"] = [control]
    protocol["aiAccess"] = {
        "conditions": {
            control: {
                "aiAllowed": False,
                "enforcement": ["locked-environment"],
                "verification": ["self-report"],
            },
            treatment: {
                "aiAllowed": True,
                "enforcement": ["none"],
                "verification": ["agent-hooks"],
            },
        },
        "deviationStrategy": "itt",
    }
    return protocol


def test_no_warnings_when_locked_and_itt(protocol):
    assert ai_access_warnings(_locked_itt(protocol)) == []


def test_no_warnings_without_control_conditions_or_ai_access(protocol):
    protocol.pop("controlConditions", None)
    protocol.pop("aiAccess", None)
    assert ai_access_warnings(protocol) == []


def test_undeclared_warns_when_control_conditions_exist(protocol):
    protocol["controlConditions"] = [protocol["conditions"][0]]
    protocol.pop("aiAccess", None)
    warnings = ai_access_warnings(protocol)
    assert [w["code"] for w in warnings] == ["ai-access-undeclared"]
    assert warnings[0]["condition"] is None
    assert warnings[0]["message"]
    assert warnings[0]["suggestions"]
    assert warnings[0]["unverifiableRoutes"] == []


_SUGGESTIONS = [
    "Lock the environment or record the screen for this condition.",
    "Analyse by assigned condition (ITT) and add a contamination sensitivity analysis.",
]


def _unverifiable_control(protocol: dict) -> tuple[str, dict]:
    control = protocol["conditions"][0]
    protocol["controlConditions"] = [control]
    protocol["aiAccess"] = _ai_access(protocol)
    (warning,) = ai_access_warnings(protocol)
    return control, warning


def test_unverifiable_lists_routes(protocol):
    control, warning = _unverifiable_control(protocol)
    assert warning["code"] == "ai-access-unverifiable"
    assert warning["condition"] == control
    assert warning["unverifiableRoutes"] == list(UNVERIFIED_ROUTES)
    assert warning["suggestions"] == _SUGGESTIONS


def test_unverifiable_message_states_design_scope_until_measured(protocol, monkeypatch):
    monkeypatch.setattr(ai_access_module, "UNVERIFIED_ROUTES_SOURCE", "design")
    control, warning = _unverifiable_control(protocol)
    assert warning["message"] == (
        f"Condition '{control}' disallows AI but relies only on channels that "
        "cannot confirm non-use. StudyLoop's IDE telemetry is not designed to "
        f"observe: {', '.join(UNVERIFIED_ROUTES)}."
    )
    assert "calibration" not in warning["message"]
    assert warning["suggestions"] == _SUGGESTIONS


def test_unverifiable_message_cites_calibration_once_measured(protocol, monkeypatch):
    monkeypatch.setattr(ai_access_module, "UNVERIFIED_ROUTES_SOURCE", "calibration")
    control, warning = _unverifiable_control(protocol)
    assert warning["message"] == (
        f"Condition '{control}' disallows AI but relies only on channels that "
        "cannot confirm non-use. In StudyLoop's calibration, IDE telemetry did "
        f"not register: {', '.join(UNVERIFIED_ROUTES)}."
    )
    assert warning["suggestions"] == _SUGGESTIONS


def test_unrecognised_routes_source_never_claims_a_calibration(protocol, monkeypatch):
    monkeypatch.setattr(ai_access_module, "UNVERIFIED_ROUTES_SOURCE", "measured?")
    _, warning = _unverifiable_control(protocol)
    assert "calibration" not in warning["message"]
    assert "not designed to observe" in warning["message"]


def test_unverifiable_message_uses_the_routes_constant(protocol, monkeypatch):
    monkeypatch.setattr(ai_access_module, "UNVERIFIED_ROUTES", ("a route", "another"))
    _, warning = _unverifiable_control(protocol)
    assert warning["unverifiableRoutes"] == ["a route", "another"]
    assert warning["message"].endswith(": a route, another.")


@pytest.mark.parametrize(
    ("enforcement", "verification"),
    [
        (["instruction"], ["screen-recording"]),
        (["instruction"], ["proctor"]),
        (["locked-environment"], ["self-report"]),
        (["screen-recording"], ["ide-telemetry"]),
        (["proctor"], ["none"]),
    ],
)
def test_recording_clears_unverifiable(protocol, enforcement, verification):
    protocol = _locked_itt(protocol)
    control = protocol["controlConditions"][0]
    entry = protocol["aiAccess"]["conditions"][control]
    entry["enforcement"] = enforcement
    entry["verification"] = verification
    assert ai_access_warnings(protocol) == []


def test_allowed_condition_is_never_unverifiable(protocol):
    protocol = _locked_itt(protocol)
    treatment = protocol["conditions"][1]
    entry = protocol["aiAccess"]["conditions"][treatment]
    entry["enforcement"] = ["none"]
    entry["verification"] = ["none"]
    assert ai_access_warnings(protocol) == []


def test_unverifiable_is_reported_per_condition_in_declared_order(protocol):
    first, second = protocol["conditions"][:2]
    protocol["aiAccess"] = {
        "conditions": {
            second: {
                "aiAllowed": False,
                "enforcement": ["none"],
                "verification": ["none"],
            },
            first: {
                "aiAllowed": False,
                "enforcement": ["instruction"],
                "verification": ["self-report"],
            },
        },
        "deviationStrategy": "itt",
    }
    warnings = ai_access_warnings(protocol)
    assert [(w["code"], w["condition"]) for w in warnings] == [
        ("ai-access-unverifiable", second),
        ("ai-access-unverifiable", first),
    ]


@pytest.mark.parametrize("strategy", ["exclusion", "per-protocol", "as-treated"])
def test_exclusion_without_sensitivity_warns(protocol, strategy):
    protocol = _locked_itt(protocol)
    protocol["aiAccess"]["deviationStrategy"] = strategy
    warnings = ai_access_warnings(protocol)
    assert [w["code"] for w in warnings] == ["deviation-without-sensitivity"]
    assert warnings[0]["condition"] is None
    assert strategy in warnings[0]["message"]
    assert warnings[0]["suggestions"]


def test_sensitivity_analysis_clears_the_deviation_warning(protocol):
    protocol = _locked_itt(protocol)
    protocol["aiAccess"]["deviationStrategy"] = "exclusion"
    protocol["aiAccess"]["sensitivityAnalysis"] = True
    assert ai_access_warnings(protocol) == []
    protocol["aiAccess"]["sensitivityAnalysis"] = False
    assert [w["code"] for w in ai_access_warnings(protocol)] == [
        "deviation-without-sensitivity"
    ]


def test_warning_shape_is_stable(protocol):
    protocol["controlConditions"] = [protocol["conditions"][0]]
    protocol["aiAccess"] = _ai_access(protocol)
    protocol["aiAccess"]["deviationStrategy"] = "exclusion"
    protocol["aiAccess"]["sensitivityAnalysis"] = False
    warnings = ai_access_warnings(protocol)
    assert [w["code"] for w in warnings] == [
        "ai-access-unverifiable",
        "deviation-without-sensitivity",
    ]
    for warning in warnings:
        assert set(warning) == {
            "code",
            "condition",
            "message",
            "unverifiableRoutes",
            "suggestions",
        }
        assert isinstance(warning["unverifiableRoutes"], list)
        assert isinstance(warning["suggestions"], list)


def test_warnings_do_not_mutate_the_protocol(protocol):
    protocol["controlConditions"] = [protocol["conditions"][0]]
    protocol["aiAccess"] = _ai_access(protocol)
    before = deepcopy(protocol)
    ai_access_warnings(protocol)
    assert protocol == before


def _policy(**over) -> dict:
    return {
        "aiAllowed": False,
        "enforcement": ["instruction"],
        "verification": ["self-report"],
        **over,
    }


def _with_access(protocol: dict, ai_access) -> dict:
    protocol["controlConditions"] = [protocol["conditions"][0]]
    protocol["aiAccess"] = ai_access
    return protocol


@pytest.mark.parametrize("ai_access", ["yes", ["x"], 5, True, 0, "", []])
def test_non_dict_ai_access_is_skipped_silently(protocol, ai_access):
    assert ai_access_warnings(_with_access(protocol, ai_access)) == []


@pytest.mark.parametrize("conditions", ["x", ["a"], None, 3, True])
def test_non_dict_conditions_are_skipped_silently(protocol, conditions):
    ai_access = {"conditions": conditions, "deviationStrategy": "itt"}
    assert ai_access_warnings(_with_access(protocol, ai_access)) == []


@pytest.mark.parametrize("policy", ["x", None, ["a"], 7, True])
def test_non_dict_policy_is_skipped_silently(protocol, policy):
    ai_access = {
        "conditions": {protocol["conditions"][0]: policy},
        "deviationStrategy": "itt",
    }
    assert ai_access_warnings(_with_access(protocol, ai_access)) == []


_NOT_A_LIST_OF_STRINGS = [
    "locked-environment",
    None,
    7,
    [1],
    [["instruction"]],
    ["instruction", None],
    {"instruction": True},
]


@pytest.mark.parametrize("bad", _NOT_A_LIST_OF_STRINGS)
@pytest.mark.parametrize("field", ["enforcement", "verification"])
def test_channels_that_are_not_a_list_of_strings_are_skipped(protocol, field, bad):
    ai_access = {
        "conditions": {protocol["conditions"][0]: _policy(**{field: bad})},
        "deviationStrategy": "itt",
    }
    assert ai_access_warnings(_with_access(protocol, ai_access)) == []


@pytest.mark.parametrize("field", ["enforcement", "verification"])
def test_missing_channels_are_skipped_silently(protocol, field):
    policy = _policy()
    del policy[field]
    ai_access = {
        "conditions": {protocol["conditions"][0]: policy},
        "deviationStrategy": "itt",
    }
    assert ai_access_warnings(_with_access(protocol, ai_access)) == []


def test_a_malformed_condition_does_not_hide_a_well_formed_one(protocol):
    first, second = protocol["conditions"][:2]
    ai_access = {
        "conditions": {first: "garbage", second: _policy()},
        "deviationStrategy": "itt",
    }
    warnings = ai_access_warnings(_with_access(protocol, ai_access))
    assert [(w["code"], w["condition"]) for w in warnings] == [
        ("ai-access-unverifiable", second)
    ]


@pytest.mark.parametrize("bad_protocol", [None, "protocol", [], 3])
def test_non_dict_protocol_yields_no_warnings(bad_protocol):
    assert ai_access_warnings(bad_protocol) == []


def test_unknown_condition_name_does_not_raise(protocol):
    ai_access = {
        "conditions": {"ghost": _policy()},
        "deviationStrategy": "itt",
    }
    warnings = ai_access_warnings(_with_access(protocol, ai_access))
    assert isinstance(warnings, list)
    assert all(isinstance(w, dict) and "code" in w for w in warnings)


@pytest.mark.parametrize("strategy", [None, 3, ["exclusion"], {"a": 1}, True])
def test_missing_or_non_string_strategy_emits_no_deviation_warning(protocol, strategy):
    protocol = _locked_itt(protocol)
    protocol["aiAccess"]["deviationStrategy"] = strategy
    assert ai_access_warnings(protocol) == []


def test_absent_strategy_emits_no_deviation_warning(protocol):
    protocol = _locked_itt(protocol)
    del protocol["aiAccess"]["deviationStrategy"]
    assert ai_access_warnings(protocol) == []
