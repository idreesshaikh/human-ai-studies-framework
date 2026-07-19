"""Load and validate study protocol YAML files against the JSON Schema.

The protocol is the machine-readable requirements specification of a study
("study-as-code"); everything downstream (instruments, lifecycle gates,
analysis plan) is derived from it.
"""

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
    """All validation errors for an in-memory protocol dict, [] when valid.

    The same schema + referential checks :func:`load_protocol` applies to a
    file, exposed for callers that hold a dict: the template registry
    (FR-TPL-1.4 instantiation) and the conversation compiler (FR-CONV-3.2
    validates on every compile). Referential checks only run once the
    document is schema-valid, mirroring the file path exactly.
    """
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
    """Parse a protocol YAML file and validate it against the schema.

    Returns the protocol as a dict. Raises :class:`ProtocolError` with a
    human-readable message naming the offending field on any failure
    (missing file, YAML syntax error, or schema violation).
    """
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
    """Cross-field integrity a JSON Schema cannot express.

    Only checked once the document is schema-valid, so field shapes can be
    assumed.
    """
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
    return errors


def uncovered_rqs(protocol: dict) -> list[str]:
    """Research-question ids no analysis-plan entry answers (FR-PROT-5).

    Traceability by construction: an RQ with no recipe is a specification
    defect the framework can surface before any data is collected.
    """
    covered = {entry["rq"] for entry in protocol["analysisPlan"]}
    return [rq["id"] for rq in protocol["researchQuestions"] if rq["id"] not in covered]
