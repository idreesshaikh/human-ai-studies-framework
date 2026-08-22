import pytest
from protocol.errors import ProtocolError
from protocol.lifecycle import (
    PHASE_ORDER,
    can_enter,
    completion_gate,
    current_phase,
    gates_by_phase,
    missing_artifacts,
)

DESIGN_DONE = {"protocol-validated.txt", "task-definitions.md"}
ETHICS_DONE = DESIGN_DONE | {"ethics-approval.pdf", "consent-form.pdf"}
PILOT_DONE = ETHICS_DONE | {"dry-run-report.md"}


def test_no_artifacts_means_first_phase(pilot):
    assert current_phase(pilot, set()) == "design"


def test_phase_advances_as_gates_are_satisfied(pilot):
    assert current_phase(pilot, DESIGN_DONE) == "ethics"
    assert current_phase(pilot, ETHICS_DONE) == "pilot"
    assert current_phase(pilot, PILOT_DONE) == "recruitment"


def test_gap_blocks_later_phases(pilot):
    # Later-phase artifacts do not compensate for a missing earlier gate.
    artifacts = PILOT_DONE - {"ethics-approval.pdf"}
    assert current_phase(pilot, artifacts) == "ethics"


def test_data_collection_refused_without_ethics_gate(pilot):
    artifacts = PILOT_DONE | {"participant-schedule.md"}
    assert can_enter(pilot, "data-collection", artifacts)
    assert not can_enter(pilot, "data-collection", artifacts - {"consent-form.pdf"})


def test_can_enter_unknown_phase_raises(pilot):
    with pytest.raises(ProtocolError, match="unknown phase"):
        can_enter(pilot, "shipping", set())


def test_missing_artifacts_lists_only_open_gates(pilot):
    missing = missing_artifacts(pilot, DESIGN_DONE | {"consent-form.pdf"})
    assert "design" not in missing
    assert missing["ethics"] == ["ethics-approval.pdf"]
    assert missing["pilot"] == ["dry-run-report.md"]


def test_all_gates_satisfied_reaches_final_phase(pilot):
    everything = {gate for phase in pilot["phases"] for gate in phase["gates"]}
    assert current_phase(pilot, everything) == PHASE_ORDER[-1]
    assert missing_artifacts(pilot, everything) == {}


def _gateless_after_ethics() -> dict:
    """
    A template-shaped protocol: gates on design and ethics only  -  the shape that
    used to auto-tick pilot through analysis on one approval.
    """
    return {
        "phases": [
            {"name": "design", "gates": ["protocol-validated.txt"]},
            {"name": "ethics", "gates": ["ethics-approval.pdf"]},
            {"name": "pilot", "gates": []},
            {"name": "recruitment", "gates": []},
            {"name": "data-collection", "gates": []},
            {"name": "analysis", "gates": []},
            {"name": "write-up", "gates": []},
        ]
    }


def test_gateless_phase_requires_explicit_advance():
    """
    FR-PROT-10: ethics approval alone must not tick pilot, recruitment, data-collection,
    and analysis  -  each needs its completion attestation.
    """
    proto = _gateless_after_ethics()
    artifacts = {"protocol-validated.txt", "ethics-approval.pdf"}
    assert current_phase(proto, artifacts) == "pilot"
    artifacts.add(completion_gate("pilot"))
    assert current_phase(proto, artifacts) == "recruitment"
    artifacts.add(completion_gate("recruitment"))
    assert current_phase(proto, artifacts) == "data-collection"
    artifacts.add(completion_gate("data-collection"))
    assert current_phase(proto, artifacts) == "analysis"
    artifacts.add(completion_gate("analysis"))
    assert current_phase(proto, artifacts) == "write-up"


def test_gateless_phases_appear_in_missing_artifacts():
    """The open-requirements list names the manual advances still owed."""
    proto = _gateless_after_ethics()
    missing = missing_artifacts(
        proto, {"protocol-validated.txt", "ethics-approval.pdf"}
    )
    assert missing["pilot"] == [completion_gate("pilot")]
    assert missing["analysis"] == [completion_gate("analysis")]


def test_final_phase_never_gets_an_implicit_gate():
    """
    There is nothing after write-up to advance to  -  no phantom open requirement on the
    last phase.
    """
    assert gates_by_phase(_gateless_after_ethics())["write-up"] == []


def test_declared_gates_are_never_replaced():
    """
    The implicit attestation only guards phases that declare nothing  -  a declared gate
    list is authoritative as-is.
    """
    proto = _gateless_after_ethics()
    assert gates_by_phase(proto)["ethics"] == ["ethics-approval.pdf"]
