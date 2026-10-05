"""Conservative evidence discovery and constraint checks, without an LLM.

Term overlap only orders discovery. Reported method use never supplies a
recommendation. Curator review and researcher confirmation are separate gates.
"""

import json
import re
from hashlib import sha256

from protocol.capture import producer_capabilities
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from middleware.db import EvidenceMapRow


class EvidenceContext(BaseModel):
    model_config = ConfigDict(extra="forbid", serialize_by_alias=True)

    query: str = Field(default="", max_length=4000)
    population: str = Field(default="", max_length=500)
    task: str = Field(default="", max_length=500)
    target_construct: str = Field(default="", alias="construct", max_length=500)
    producers: list[str] = Field(default_factory=list, max_length=30)
    instruments: list[str] = Field(default_factory=list, max_length=30)
    confirmedRelationIds: list[str] = Field(default_factory=list, max_length=100)


class EvidenceProposal(EvidenceContext):
    candidateId: str = Field(max_length=200)
    mapDigest: str = Field(max_length=64)
    requestId: str = Field(min_length=1, max_length=100)


def digest(document: dict) -> str:
    return sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()


def latest_map(session, study_id):
    return session.scalar(
        select(EvidenceMapRow)
        .where(
            EvidenceMapRow.study_id == study_id,
        )
        .order_by(EvidenceMapRow.id.desc())
    )


def evidence_export(session, study_id):
    return [
        {"digest": row.digest, "document": row.document}
        for row in session.scalars(
            select(EvidenceMapRow)
            .where(
                EvidenceMapRow.study_id == study_id,
            )
            .order_by(EvidenceMapRow.id)
        )
    ]


def _words(text):
    return set(re.findall(r"[a-z0-9]+", text.casefold())) - {
        "a",
        "an",
        "the",
        "is",
        "does",
        "with",
        "and",
        "of",
        "in",
        "to",
    }


def rank_candidates(document: dict, context: EvidenceContext) -> list[dict]:
    import analysis.recipes  # noqa: F401 - registers supported recipes
    from analysis.core import REGISTRY

    known_producers = producer_capabilities({})
    publications = {p["id"]: p for p in document["publications"]}
    candidates = []
    for study in document["studies"]:
        family = study["designFamily"]
        relevant = [
            r
            for r in document["relations"]
            if r["studyId"] == study["id"] and r["target"] == family
        ]
        support = [
            r
            for r in relevant
            if r["review"]["status"] == "reviewed"
            and r["kind"] != "reported-method-use"
            and r["applicability"]["status"] in ("compatible", "conditional")
        ]
        reasons, missing, constraints = [], [], []
        incompatible = any(
            r["review"]["status"] == "reviewed"
            and r["kind"] != "reported-method-use"
            and r["applicability"]["status"] == "incompatible"
            for r in relevant
        )
        if incompatible:
            reasons.append(
                "Reviewed evidence includes an incompatibility; "
                "resolve it before choosing."
            )
        if not support:
            missing.append("Reviewed applicability guidance for this design")
        for relation in support:
            applicability = relation["applicability"]
            reasons.extend(applicability["reasons"])
            constraints.extend(applicability["constraints"])
            missing.extend(applicability["missingFacts"])
            if relation["id"] not in context.confirmedRelationIds:
                missing.append(f"Confirm source context: {relation['id']}")
        for name, supplied, recorded in (
            ("population", context.population, study["population"]),
            ("task", context.task, "; ".join(study["tasks"] or [])),
            ("construct", context.target_construct, "; ".join(study["constructs"])),
        ):
            if not supplied.strip() or not recorded:
                missing.append(f"Known {name} and a source-context match")
            elif supplied.strip().casefold() not in {
                item.strip().casefold() for item in recorded.split("; ")
            }:
                missing.append(
                    f"{name.capitalize()} differs; "
                    "transferability has not been established"
                )
        for capture in study["captureRequirements"]:
            producer = capture["producer"]
            if capture["availability"] == "unavailable":
                incompatible = True
                reasons.append(f"Capture unavailable for {capture['measureId']}")
            elif capture["availability"] == "unknown" or not producer:
                missing.append(f"Capture availability for {capture['measureId']}")
            elif producer not in known_producers:
                incompatible = True
                reasons.append(f"Unsupported producer: {producer}")
            elif producer not in context.producers:
                incompatible = True
                reasons.append(f"Missing producer: {producer}")
            elif capture["availability"] == "external":
                constraints.append(f"Arrange external capture: {producer}")
        for measure in study["measures"]:
            if measure["analysisRecipe"] and measure["analysisRecipe"] not in REGISTRY:
                incompatible = True
                reasons.append(
                    f"Unsupported analysis recipe: {measure['analysisRecipe']}"
                )
            elif measure["analysisRecipe"]:
                required = REGISTRY[measure["analysisRecipe"]].requires.events
                captured = {
                    event
                    for c in study["captureRequirements"]
                    for event in c["eventTypes"] or []
                }
                for event in sorted(required - captured):
                    missing.append(f"Missing recipe input event: {event}")
                metric_inputs = REGISTRY[measure["analysisRecipe"]].requires.metrics
                fields = {
                    field
                    for m in study["measures"]
                    for field in m["datasetFields"] or []
                }
                for metric in sorted(metric_inputs - fields):
                    missing.append(f"Missing recipe input metric: {metric}")
                recipe_family = {
                    "paired-nonparametric": "within-subjects",
                    "two-group-nonparametric": "between-subjects",
                }.get(measure["analysisRecipe"])
                if recipe_family and recipe_family != family:
                    incompatible = True
                    reasons.append(
                        "The mapped analysis assumptions conflict "
                        "with the design family."
                    )
            if not any(
                c["measureId"] == measure["id"] for c in study["captureRequirements"]
            ):
                missing.append(f"Capture requirements for {measure['id']}")
            if not measure["instrument"]:
                missing.append(f"Instrument for {measure['id']}")
            elif measure["instrument"] not in context.instruments:
                incompatible = True
                reasons.append(f"Missing instrument: {measure['instrument']}")
        if family not in ("within-subjects", "between-subjects"):
            missing.append("An executable design family supported by this platform")
        status = (
            "incompatible"
            if incompatible
            else "insufficient-evidence"
            if missing
            else "conditional"
            if constraints
            or any(r["applicability"]["status"] == "conditional" for r in support)
            else "compatible"
        )
        searchable = " ".join(
            [
                *study["researchQuestions"],
                study["population"] or "",
                *(study["tasks"] or []),
                *study["constructs"],
            ]
        )
        candidates.append(
            {
                "id": study["id"],
                "designFamily": family,
                "status": status,
                "discoveryScore": len(
                    _words(context.query).intersection(_words(searchable))
                ),
                "reasons": list(dict.fromkeys(reasons)),
                "missingFacts": list(dict.fromkeys(missing)),
                "constraints": list(dict.fromkeys(constraints)),
                "study": study,
                "sources": [
                    {**r, "publication": publications[r["passage"]["publicationId"]]}
                    for r in relevant
                ],
            }
        )
    order = {
        "compatible": 0,
        "conditional": 1,
        "insufficient-evidence": 2,
        "incompatible": 3,
    }
    return sorted(
        candidates, key=lambda c: (order[c["status"]], -c["discoveryScore"], c["id"])
    )
