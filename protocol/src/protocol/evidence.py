"""Versioned study/evidence contract; discovery scores are not evidence quality.

This is a separate document from the executable protocol. It does not change
protocol approval, claim scientific review, or infer missing study facts.
"""

import json
from pathlib import Path

import jsonschema
import yaml

from protocol.errors import ProtocolError


def _object(properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties) if required is None else required,
    }


def _list(items: dict, *, minimum: int = 0) -> dict:
    return {"type": "array", "items": items, "minItems": minimum}


TEXT = {"type": "string", "minLength": 1, "pattern": r"\S"}
UNKNOWN_TEXT = {"anyOf": [TEXT, {"type": "null"}]}
TEXTS = _list(TEXT)

EVIDENCE_MAP_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://phoenix-tern.dev/schemas/study-evidence-map-v1.json",
    **_object(
        {
            "schemaVersion": {"const": 1},
            "mapId": TEXT,
            "mapVersion": TEXT,
            "description": TEXT,
            "publications": _list({"$ref": "#/$defs/publication"}, minimum=1),
            "studies": _list({"$ref": "#/$defs/study"}),
            "relations": _list({"$ref": "#/$defs/relation"}),
        }
    ),
    "$defs": {
        "publication": _object(
            {"id": TEXT, "source": TEXT, "title": TEXT, "version": UNKNOWN_TEXT}
        ),
        "measure": _object(
            {
                "id": TEXT,
                "construct": TEXT,
                "definition": UNKNOWN_TEXT,
                "instrument": UNKNOWN_TEXT,
                "datasetFields": {"anyOf": [TEXTS, {"type": "null"}]},
                "analysisRecipe": UNKNOWN_TEXT,
            }
        ),
        "capture": _object(
            {
                "measureId": TEXT,
                "producer": UNKNOWN_TEXT,
                "eventTypes": {"anyOf": [TEXTS, {"type": "null"}]},
                "availability": {
                    "enum": ["available", "external", "unavailable", "unknown"]
                },
            }
        ),
        "study": _object(
            {
                "id": TEXT,
                "publicationIds": {**TEXTS, "minItems": 1, "uniqueItems": True},
                "researchQuestions": TEXTS,
                "designFamily": UNKNOWN_TEXT,
                "population": UNKNOWN_TEXT,
                "tasks": {"anyOf": [TEXTS, {"type": "null"}]},
                "conditions": {"anyOf": [TEXTS, {"type": "null"}]},
                "constructs": TEXTS,
                "measures": _list({"$ref": "#/$defs/measure"}),
                "analysisAssumptions": {"anyOf": [TEXTS, {"type": "null"}]},
                "limitations": {"anyOf": [TEXTS, {"type": "null"}]},
                "captureRequirements": _list({"$ref": "#/$defs/capture"}),
            }
        ),
        "relation": _object(
            {
                "id": TEXT,
                "studyId": UNKNOWN_TEXT,
                "target": TEXT,
                "kind": {
                    "enum": [
                        "reported-method-use",
                        "methodological-guidance",
                        "measurement-validity",
                        "conditional-applicability",
                    ]
                },
                "claimType": {
                    "enum": ["reported-fact", "interpretation", "recommendation"]
                },
                "claim": TEXT,
                "passage": _object(
                    {"publicationId": TEXT, "location": TEXT, "text": TEXT}
                ),
                "review": _object(
                    {
                        "status": {"enum": ["unreviewed", "reviewed", "disputed"]},
                        "reviewers": {**TEXTS, "uniqueItems": True},
                        "notes": UNKNOWN_TEXT,
                    }
                ),
                "extractionConfidence": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "maximum": 1,
                },
                "evidenceQuality": {
                    "enum": ["unknown", "limited", "moderate", "strong"]
                },
                "applicability": _object(
                    {
                        "status": {
                            "enum": [
                                "compatible",
                                "conditional",
                                "incompatible",
                                "unknown",
                            ]
                        },
                        "context": TEXT,
                        "reasons": TEXTS,
                        "constraints": TEXTS,
                        "missingFacts": TEXTS,
                    }
                ),
            }
        ),
    },
}


def evidence_map_schema() -> dict:
    """Return an independent JSON-serializable copy for clients and exports."""
    return json.loads(json.dumps(EVIDENCE_MAP_SCHEMA))


def validate_evidence_map(data: object) -> list[str]:
    """Validate shape, source identity, review provenance and local references."""
    validator = jsonschema.Draft202012Validator(EVIDENCE_MAP_SCHEMA)
    errors = [
        f"{'.'.join(map(str, error.absolute_path)) or '(document root)'}: "
        f"{error.message}"
        for error in sorted(
            validator.iter_errors(data),
            key=lambda error: tuple(map(str, error.absolute_path)),
        )
    ]
    if errors:
        return errors
    publications = {p["id"] for p in data["publications"]}
    studies = {s["id"] for s in data["studies"]}
    for collection in ("publications", "studies", "relations"):
        ids = [entry["id"] for entry in data[collection]]
        if len(ids) != len(set(ids)):
            errors.append(f"{collection}: duplicate id")
    sources = [p["source"] for p in data["publications"]]
    if len(sources) != len(set(sources)):
        errors.append("publications: duplicate stable source; reuse its publication id")
    for study in data["studies"]:
        for pub in study["publicationIds"]:
            if pub not in publications:
                errors.append(f"study {study['id']}: unknown publication {pub}")
        measures = [m["id"] for m in study["measures"]]
        if len(measures) != len(set(measures)):
            errors.append(f"study {study['id']}: duplicate measure id")
        for measure in study["measures"]:
            if measure["construct"] not in study["constructs"]:
                errors.append(f"study {study['id']}: unknown measure construct")
        for capture in study["captureRequirements"]:
            if capture["measureId"] not in measures:
                errors.append(f"study {study['id']}: unknown capture measure")
    for relation in data["relations"]:
        label = f"relation {relation['id']}"
        if relation["studyId"] is not None and relation["studyId"] not in studies:
            errors.append(f"{label}: unknown study")
        if relation["passage"]["publicationId"] not in publications:
            errors.append(f"{label}: unknown passage publication")
        review = relation["review"]
        applicability = relation["applicability"]
        if review["status"] == "reviewed" and not review["reviewers"]:
            errors.append(f"{label}: reviewed evidence needs an identified reviewer")
        if review["status"] != "reviewed" and applicability["status"] != "unknown":
            errors.append(
                f"{label}: unreviewed or disputed applicability must be unknown"
            )
        if applicability["status"] != "unknown" and not applicability["reasons"]:
            errors.append(f"{label}: an applicability decision needs reasons")
        if applicability["status"] == "conditional" and not (
            applicability["constraints"] or applicability["missingFacts"]
        ):
            errors.append(
                f"{label}: conditional applicability needs explicit conditions"
            )
        if relation["kind"] == "reported-method-use" and relation["claimType"] != (
            "reported-fact"
        ):
            errors.append(f"{label}: reported method use must be a reported fact")
    return errors


def load_evidence_map(path: str | Path) -> dict:
    """Load JSON or YAML, rejecting invalid documents without filling unknowns."""
    try:
        data = yaml.safe_load(Path(path).read_text("utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ProtocolError(f"cannot read evidence map {path}: {exc}") from exc
    errors = validate_evidence_map(data)
    if errors:
        raise ProtocolError("invalid evidence map:\n" + "\n".join(errors))
    return data
