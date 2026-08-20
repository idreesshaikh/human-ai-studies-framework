"""The validity-threats record (FR-CUR-3)."""

from __future__ import annotations

from dataclasses import dataclass, field

from curated.contract import SamplingFrame
from curated.heuristics import heuristic_records


@dataclass
class Bias:
    """
    A declared bias: its direction and either a mitigation or an explicit acceptance.
    """

    description: str
    direction: str
    mitigation: str = ""
    accepted: str = ""


# Bias starter entries the miner is prompted to confirm or revise - so the known
# provenance pitfalls of GitHub mining are never silently omitted.
STARTER_BIASES: tuple[Bias, ...] = (
    Bias(
        description=(
            "Agent authorship is inferred from surface signals, not ground "
            "truth; some agent activity is unlabeled and some human activity "
            "is mislabeled as agent."
        ),
        direction="uncertain (both false-positive and false-negative)",
        mitigation="heuristics named and versioned; verdicts auditable per event",
    ),
    Bias(
        description=(
            "The search frame favors public, active repositories; private "
            "and archived work is invisible."
        ),
        direction="under-samples private / low-activity contexts",
        accepted="scope is public open-source by design; stated as a limit",
    ),
    Bias(
        description=(
            "Merged-PR mining conditions on acceptance; abandoned agent "
            "attempts are absent, flattering agent success rates."
        ),
        direction="over-states agent success",
        mitigation="report closed/unmerged coverage alongside merged",
    ),
)


@dataclass
class CoverageRecord:
    requested: int
    retrieved: int
    dropped: dict[str, int] = field(default_factory=dict)


@dataclass
class ThreatsRecord:
    """The full record."""

    sampling_frame: SamplingFrame
    fired_heuristic_ids: set[str]
    coverage: CoverageRecord
    biases: list[Bias] = field(default_factory=list)
    actor_unit_note: str = ""

    def to_doc(self) -> dict:
        return {
            "samplingFrame": {
                "query": self.sampling_frame.query,
                "window": {
                    "start": self.sampling_frame.window_start,
                    "end": self.sampling_frame.window_end,
                },
                "inclusionRules": list(self.sampling_frame.inclusion_rules),
                "exclusions": list(self.sampling_frame.exclusions),
                "actorUnit": self.sampling_frame.actor_unit,
                "contentPolicy": self.sampling_frame.content_policy,
                "actorUnitWindowing": self.actor_unit_note,
            },
            "heuristics": heuristic_records(self.fired_heuristic_ids),
            "biases": [
                {
                    "description": b.description,
                    "direction": b.direction,
                    **({"mitigation": b.mitigation} if b.mitigation else {}),
                    **({"accepted": b.accepted} if b.accepted else {}),
                }
                for b in self.biases
            ],
            "coverage": {
                "requested": self.coverage.requested,
                "retrieved": self.coverage.retrieved,
                "dropped": dict(self.coverage.dropped),
            },
        }


def build_record(
    frame: SamplingFrame,
    fired_heuristic_ids: set[str],
    requested: int,
    retrieved: int,
    dropped: dict[str, int],
    biases: list[Bias] | None = None,
    actor_unit_note: str = "",
) -> ThreatsRecord:
    """
    Assemble the record after a run: coverage + heuristics are generated here;
    ``biases`` default to the starter set (the researcher revises them, but the section
    is never empty).
    """
    return ThreatsRecord(
        sampling_frame=frame,
        fired_heuristic_ids=set(fired_heuristic_ids),
        coverage=CoverageRecord(
            requested=requested, retrieved=retrieved, dropped=dropped
        ),
        biases=list(biases) if biases is not None else list(STARTER_BIASES),
        actor_unit_note=actor_unit_note or _default_actor_unit_note(frame.actor_unit),
    )


def _default_actor_unit_note(actor_unit: str) -> str:
    return {
        "developer": (
            "participantId = the pseudonymized commit/PR author; a developer "
            "who authors across several activity units keeps one id."
        ),
        "repo": (
            "participantId = the pseudonymized repository; all activity in a "
            "repo shares one id."
        ),
        "agent": (
            "participantId = the pseudonymized agent identity; commit-batch "
            "windows group an agent's contiguous activity into one sessionId."
        ),
    }.get(actor_unit, f"participantId = the pseudonymized {actor_unit}.")


def validate_record_doc(doc: dict) -> list[str]:
    """Return a list of problems with a threats-record doc (empty = valid)."""
    problems: list[str] = []
    if not isinstance(doc, dict):
        return ["the validity-threats record must be a mapping"]
    if not doc.get("samplingFrame", {}).get("query"):
        problems.append("samplingFrame.query is missing")
    biases = doc.get("biases")
    if not biases:
        problems.append(
            "biases is empty — declare at least the known provenance biases "
            "(the starter entries are a floor, not a ceiling)"
        )
    else:
        for i, b in enumerate(biases):
            if not (b.get("mitigation") or b.get("accepted")):
                problems.append(
                    f"biases[{i}] has neither a mitigation nor an explicit "
                    "acceptance — an unaddressed bias is not honestly recorded"
                )
    if "coverage" not in doc:
        problems.append("coverage is missing (requested/retrieved/dropped)")
    return problems
