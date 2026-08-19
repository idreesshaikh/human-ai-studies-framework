"""Study lifecycle state machine.

Phases run in the fixed order ``design -> ethics -> pilot -> recruitment ->
data-collection -> analysis -> write-up``. Each phase in the protocol YAML
declares ``gates``: the artifact names that must exist before the study may
progress *past* that phase. Gates are requirements-validation checkpoints:
the study's requirements (ethics approval, consent template, ...) are
validated as satisfied before the next phase may be entered.

A phase that declares no gates is guarded by an implicit completion
attestation (FR-PROT-10): the researcher must explicitly advance past it —
one ethics approval must not silently tick pilot, recruitment,
data-collection, and analysis all at once. The current phase stays a pure
function of the artifact set (FR-DASH-2: computed, never hand-set); the
manual advance simply *is* an artifact. The final phase needs none — there
is nothing after it to advance to.
"""

import itertools

from protocol.errors import ProtocolError

PHASE_ORDER: tuple[str, ...] = (
    "design",
    "ethics",
    "pilot",
    "recruitment",
    "data-collection",
    "analysis",
    "write-up",
)


def completion_gate(phase: str) -> str:
    """The implicit gate artifact guarding a phase that declares none.
    Written by the researcher's explicit advance (attestation or upload)."""
    return f"{phase}-complete.txt"


def gates_by_phase(protocol: dict) -> dict[str, list[str]]:
    """Map each lifecycle phase to the gate artifacts that guard it: the
    declared ones, or the implicit completion attestation when a non-final
    phase declares none (every transition is guarded, FR-PROT-3)."""
    declared = {p["name"]: list(p.get("gates", [])) for p in protocol["phases"]}
    return {
        phase: declared.get(phase)
        or ([completion_gate(phase)] if phase != PHASE_ORDER[-1] else [])
        for phase in PHASE_ORDER
    }


def _check_phase(phase: str) -> None:
    if phase not in PHASE_ORDER:
        raise ProtocolError(
            f"unknown phase {phase!r}; phases are {', '.join(PHASE_ORDER)}"
        )


def current_phase(protocol: dict, artifacts: set[str]) -> str:
    """Return the furthest phase whose predecessors' gates are all satisfied.

    Gates are requirements-validation checkpoints: a phase is reachable only
    once every artifact required by every earlier phase is present in
    ``artifacts``.
    """
    gates = gates_by_phase(protocol)
    reached = PHASE_ORDER[0]
    for prev, phase in itertools.pairwise(PHASE_ORDER):
        if any(gate not in artifacts for gate in gates[prev]):
            break
        reached = phase
    return reached


def missing_artifacts(protocol: dict, artifacts: set[str]) -> dict[str, list[str]]:
    """Map each phase to its gate artifacts not yet present in ``artifacts``.

    Only phases with at least one missing artifact appear in the result.
    Gates are requirements-validation checkpoints, so this is the study's
    open-requirements list.
    """
    gates = gates_by_phase(protocol)
    return {
        phase: missing
        for phase in PHASE_ORDER
        if (missing := [g for g in gates[phase] if g not in artifacts])
    }


def can_enter(protocol: dict, phase: str, artifacts: set[str]) -> bool:
    """Whether ``phase`` may be entered given the artifacts produced so far.

    True iff the gates (requirements-validation checkpoints) of every
    preceding phase are satisfied - e.g. ``data-collection`` is refused while
    the ethics phase's approval artifacts are missing.
    """
    _check_phase(phase)
    gates = gates_by_phase(protocol)
    predecessors = PHASE_ORDER[: PHASE_ORDER.index(phase)]
    return all(gate in artifacts for prev in predecessors for gate in gates[prev])
