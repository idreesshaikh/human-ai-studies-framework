"""Load and validate study protocol YAML files against the JSON Schema."""

import json
from functools import cache
from importlib import resources
from pathlib import Path

import jsonschema
import yaml

from protocol.errors import ProtocolError

_SCHEMA_RESOURCE = "schema/study-protocol.schema.json"


@cache
def load_schema() -> dict:
    """Return the bundled study-protocol JSON Schema (draft 2020-12)."""
    schema_text = (
        resources.files("protocol").joinpath(_SCHEMA_RESOURCE).read_text("utf-8")
    )
    return json.loads(schema_text)


def _field_path(error: jsonschema.ValidationError) -> str:
    """Dotted path to the offending field, e.g. ``participants.design``."""
    parts = [str(p) for p in error.absolute_path]
    return ".".join(parts) if parts else "(document root)"


def validate_protocol(data: dict) -> list[str]:
    """All validation errors for an in-memory protocol dict, [] when valid."""
    if not isinstance(data, dict):
        return [f"protocol must be a mapping, got {type(data).__name__}"]
    validator = jsonschema.Draft202012Validator(load_schema())
    schema_errors = [
        f"{_field_path(err)}: {err.message}"
        for err in sorted(
            validator.iter_errors(data), key=lambda e: list(e.absolute_path)
        )
    ]
    return schema_errors or _referential_errors(data)


def load_protocol(path: str | Path) -> dict:
    """Parse a protocol YAML file and validate it against the schema."""
    path = Path(path)
    try:
        text = path.read_text("utf-8")
    except OSError as exc:
        raise ProtocolError(f"cannot read protocol file {path}: {exc}") from exc

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ProtocolError(f"invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ProtocolError(
            f"protocol file {path} must contain a YAML mapping at the top "
            f"level, got {type(data).__name__}"
        )

    errors = validate_protocol(data)
    if errors:
        lines = [f"protocol file {path} is invalid:"]
        lines += [f"  - {err}" for err in errors]
        raise ProtocolError("\n".join(lines))

    return data


def _referential_errors(data: dict) -> list[str]:
    """Cross-field integrity a JSON Schema cannot express."""
    errors = []
    rq_ids = {rq["id"] for rq in data["researchQuestions"]}
    for i, entry in enumerate(data["analysisPlan"]):
        if entry["rq"] not in rq_ids:
            errors.append(
                f"analysisPlan.{i}.rq: {entry['rq']!r} is not a declared "
                f"research question (declared: {', '.join(sorted(rq_ids))})"
            )
    names = [p["name"] for p in data["phases"]]
    for name in sorted({n for n in names if names.count(n) > 1}):
        errors.append(f"phases: phase {name!r} is declared more than once")
    capture = data.get("capture") or {}
    from protocol.capture import producer_capabilities, required_producers

    producers = producer_capabilities(data)
    required = required_producers(data, producers)
    for producer in required:
        entry = producers.get(producer)
        if entry is None:
            errors.append(f"capture.requiredProducers: unknown producer {producer!r}")
        elif entry["state"] in {"unavailable", "unsupported", "disabled"}:
            errors.append(
                f"capture.requiredProducers: {producer!r} is {entry['state']}"
            )
    policy = (capture.get("privacy") or {}).get("agentContentPolicy")
    if policy == "full" and not (data.get("instruments", {}).get("agentCapture")):
        errors.append(
            "capture.privacy.agentContentPolicy: full requires instruments.agentCapture"
        )
    return errors


def uncovered_rqs(protocol: dict) -> list[str]:
    """Research-question ids no analysis-plan entry answers (FR-PROT-5)."""
    covered = {entry["rq"] for entry in protocol["analysisPlan"]}
    return [rq["id"] for rq in protocol["researchQuestions"] if rq["id"] not in covered]
