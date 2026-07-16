import pytest
from protocol.errors import ProtocolError
from protocol.lifecycle import (
    PHASE_ORDER,
    can_enter,
    current_phase,
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
