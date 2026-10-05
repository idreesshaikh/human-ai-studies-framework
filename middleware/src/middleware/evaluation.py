"""Offline research evaluation contracts. No classifier is promoted implicitly."""

import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Callable
from typing import Literal

from protocol.evidence import validate_evidence_map
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from middleware.evidence_mapping import EvidenceContext, digest, rank_candidates

Status = Literal["compatible", "conditional", "incompatible", "insufficient-evidence"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Case(StrictModel):
    id: str = Field(min_length=1)
    scenario_family: str = Field(min_length=1)
    split: Literal["train", "calibration", "test"]
    study_ids: list[str] = Field(min_length=1)
    context: EvidenceContext
    expected: dict[str, Status] = Field(min_length=1)


class Benchmark(StrictModel):
    version: str = Field(min_length=1)
    map_digest: str
    label_provenance: Literal["synthetic", "human-adjudicated", "draft"]
    reviewers: list[str]
    review_notes: str = Field(min_length=1)
    cases: list[Case] = Field(min_length=1)

    def verify(self, evidence: dict, *, allow_synthetic: bool = False) -> None:
        errors = validate_evidence_map(evidence)
        if errors:
            raise ValueError("Invalid evidence map: " + "; ".join(errors))
        if digest(evidence) != self.map_digest:
            raise ValueError("Evidence snapshot digest changed")
        if self.label_provenance != "human-adjudicated" and not (
            allow_synthetic and self.label_provenance == "synthetic"
        ):
            raise ValueError("Research evaluation requires human-adjudicated labels")
        if (
            self.label_provenance == "human-adjudicated"
            and len(set(self.reviewers)) < 2
        ):
            raise ValueError("Record two independent reviewers and adjudication notes")
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate case id")
        studies = {study["id"]: study for study in evidence["studies"]}
        families: dict[str, str] = {}
        for case in self.cases:
            if not set(case.study_ids) <= studies.keys() or not set(
                case.expected
            ) <= set(case.study_ids):
                raise ValueError("Case references an unknown or undeclared study")
            # Conservative grouping also prevents reports of one underlying study
            # crossing boundaries under different study IDs. Reserve shared reports.
            keys = [f"scenario:{case.scenario_family}"]
            for study in case.study_ids:
                keys.append(f"study:{study}")
                keys.extend(
                    f"publication:{p}" for p in studies[study]["publicationIds"]
                )
            for key in keys:
                if key in families and families[key] != case.split:
                    raise ValueError(f"Split leakage: {key}")
                families[key] = case.split

    def digest(self) -> str:
        encoded = json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(encoded.encode()).hexdigest()


class Prediction(StrictModel):
    case_id: str
    candidate_id: str
    status: Status | None  # None is explicit abstention, not a missing row.
    confidence: float | None = Field(default=None, ge=0, le=1)
    latency_ms: float = Field(ge=0, allow_inf_nan=False)
    cost_usd: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    error: str | None = None


def score(
    benchmark: Benchmark, predictions: list[Prediction], *, split: str = "test"
) -> dict:
    expected = {
        (case.id, candidate): status
        for case in benchmark.cases
        if case.split == split
        for candidate, status in case.expected.items()
    }
    if not expected:
        raise ValueError("No cases in selected split")
    indexed = {(row.case_id, row.candidate_id): row for row in predictions}
    if len(indexed) != len(predictions) or indexed.keys() != expected.keys():
        raise ValueError("Predictions must cover each held-out decision exactly once")
    confusion = defaultdict(Counter)
    automated = errors = unsafe = failures = 0
    latencies = []
    costs = []
    calibration = []
    for key, reference in expected.items():
        row = indexed[key]
        confusion[reference][row.status or "abstain"] += 1
        latencies.append(row.latency_ms)
        if row.cost_usd is not None:
            costs.append(row.cost_usd)
        if row.error:
            failures += 1
        if row.status is not None:
            automated += 1
            wrong = row.status != reference
            errors += wrong
            unsafe += row.status in {"compatible", "conditional"} and reference in {
                "incompatible",
                "insufficient-evidence",
            }
            if row.confidence is not None:
                calibration.append((row.confidence - (not wrong)) ** 2)
    latencies.sort()
    count = len(expected)
    return {
        "benchmarkDigest": benchmark.digest(),
        "evidenceDigest": benchmark.map_digest,
        "labelProvenance": benchmark.label_provenance,
        "split": split,
        "decisions": count,
        "automatedCoverage": automated / count,
        "errorAmongAutomated": errors / automated if automated else None,
        "unsupportedRecommendations": unsafe,
        "providerFailures": failures,
        "confusion": {key: dict(value) for key, value in sorted(confusion.items())},
        "brierCorrectness": sum(calibration) / len(calibration)
        if calibration
        else None,
        "p95LatencyMs": latencies[math.ceil(count * 0.95) - 1],
        "costUsd": sum(costs) if len(costs) == count else None,
        "costKnownDecisions": len(costs),
        "limits": (
            "Declared adjudication is not reviewer authentication. "
            "Synthetic scores test software only; citation support, protocol "
            "feasibility, correction effort and uncertainty need independent review."
        ),
    }


def rules_predictions(
    benchmark: Benchmark, evidence: dict, *, split: str = "test"
) -> list[Prediction]:
    from time import perf_counter

    rows = []
    for case in benchmark.cases:
        if case.split != split:
            continue
        started = perf_counter()
        ranked = {
            candidate["id"]: candidate
            for candidate in rank_candidates(evidence, case.context)
        }
        elapsed = (perf_counter() - started) * 1000
        for candidate in case.expected:
            rows.append(
                Prediction(
                    case_id=case.id,
                    candidate_id=candidate,
                    status=ranked[candidate]["status"],
                    latency_ms=elapsed,
                    cost_usd=0,
                )
            )
    return rows


def reviewer_agreement(first: dict[str, Status], second: dict[str, Status]) -> dict:
    """Descriptive agreement for actual independent ratings, not generated labels."""
    validator = TypeAdapter(dict[str, Status])
    first, second = validator.validate_python(first), validator.validate_python(second)
    if not first or first.keys() != second.keys():
        raise ValueError("Reviewers must rate the same non-empty decision set")
    count = len(first)
    observed = sum(first[key] == second[key] for key in first) / count
    a, b = Counter(first.values()), Counter(second.values())
    chance = sum(a[label] * b[label] for label in a.keys() | b.keys()) / count**2
    return {
        "decisions": count,
        "agreement": observed,
        "cohenKappa": (observed - chance) / (1 - chance) if chance < 1 else None,
        "disagreements": sorted(key for key in first if first[key] != second[key]),
    }


class ModelDecision(StrictModel):
    candidate_id: str
    status: Status | None
    confidence: float | None = Field(default=None, ge=0, le=1)


class ModelDecisions(StrictModel):
    decisions: list[ModelDecision]


def model_predictions(
    benchmark: Benchmark,
    evidence: dict,
    request: Callable[[str], dict],
    *,
    stages: int = 1,
) -> list[Prediction]:
    """Experimental direct/propose-critic adapters; never apply model outputs."""
    from time import perf_counter

    if stages not in {1, 2}:
        raise ValueError(
            "Only bounded direct or propose-critic experiments are supported"
        )
    predictions = []
    for case in benchmark.cases:
        if case.split != "test":
            continue
        # The model receives frozen evidence and constraints, never gold labels.
        prompt = json.dumps(
            {
                "context": case.context.model_dump(),
                "candidate_ids": list(case.expected),
                "evidence": evidence,
            }
        )
        started = perf_counter()
        error = None
        decisions = {}
        try:
            result = ModelDecisions.model_validate(request(prompt))
            if stages == 2:
                result = ModelDecisions.model_validate(
                    request(
                        "Independently critique the proposed decisions against "
                        "the same "
                        "evidence. Correct unsupported choices or abstain.\n"
                        + prompt
                        + "\nProposals: "
                        + result.model_dump_json()
                    )
                )
            decisions = {row.candidate_id: row for row in result.decisions}
            if (
                len(decisions) != len(result.decisions)
                or decisions.keys() != case.expected.keys()
            ):
                raise ValueError("Model omitted, duplicated, or invented a candidate")
        except Exception as exc:  # noqa: BLE001 - provider/schema failure is explicit abstention
            error = type(exc).__name__
            decisions = {}
        elapsed = (perf_counter() - started) * 1000
        for candidate in case.expected:
            decision = decisions.get(candidate)
            predictions.append(
                Prediction(
                    case_id=case.id,
                    candidate_id=candidate,
                    status=decision.status if decision else None,
                    confidence=decision.confidence if decision else None,
                    latency_ms=elapsed,
                    cost_usd=None,
                    error=error,
                )
            )
    return predictions
