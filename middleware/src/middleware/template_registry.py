"""The template registry.

Templates are versioned YAML documents in ``templates/registry/``, each
encoding one published, citable study design - its parameters, measures,
statistical plan, and a ``protocolSkeleton`` that instantiates into a
protocol passing ``protocol validate`` with zero hand edits (F1.1).
Validation is two-layered:

- **Registry validation** (:func:`validate_registry`): the template JSON
  Schema, mandatory citations, and - earlier than instantiation, per F2.3 -
  every recipe the skeleton's ``analysisPlan`` names must exist in the
  analysis catalogue. A template cannot promise an analysis the platform
  can't run.
- **Instantiation validation**: parameter typing/bounds, then the filled
  protocol through :func:`protocol.loader.validate_protocol` (the same
  checks the CLI applies to a file).

Instantiation is a pure function of (template, parameters) - the FR-CONV-3
compiler treats a template instantiation as a batch of design moves, so the
same determinism guarantee (byte-identical replay) holds here. Which
template@version produced a draft is recorded in the draft's generated
header comment and the compilation row, never guessed (F1.3).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import jsonschema
import yaml

log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parent.parent.parent.parent
REGISTRY_DIR = REPO / "templates" / "registry"
SCHEMA_FILE = REPO / "templates" / "schemas" / "template.schema.json"

#: Exact-placeholder form: the whole scalar is one parameter reference, so
#: the *typed* value (int, list, ...) replaces the string wholesale.
_EXACT_PLACEHOLDER = re.compile(r"^\{\{\s*(\w+)\s*\}\}$")
#: Embedded form: interpolated into the surrounding text.
_EMBEDDED_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


class TemplateError(Exception):
    """A template problem with a human-readable message (mirrors
    ``protocol.errors.ProtocolError``'s posture)."""


def _load_schema() -> dict:
    return json.loads(SCHEMA_FILE.read_text("utf-8"))


def _read_all() -> list[tuple[Path, dict]]:
    """Every registry document, unvalidated, sorted by filename for
    deterministic listings."""
    docs = []
    for path in sorted(REGISTRY_DIR.glob("*.yaml")):
        try:
            doc = yaml.safe_load(path.read_text("utf-8"))
        except yaml.YAMLError as exc:
            raise TemplateError(f"invalid YAML in {path.name}: {exc}") from exc
        if isinstance(doc, dict):
            docs.append((path, doc))
    return docs


def load_template(template_id: str, version: int | None = None) -> dict:
    """Load one template by id; highest ``templateVersion`` unless pinned.

    Loading an old version after a newer one exists keeps working (F1.3) -
    versions are separate documents, never overwritten.
    """
    candidates = [
        doc
        for _, doc in _read_all()
        if doc.get("templateId") == template_id
        and (version is None or doc.get("templateVersion") == version)
    ]
    if not candidates:
        pin = f" version {version}" if version is not None else ""
        raise TemplateError(
            f"template {template_id!r}{pin} not found in {REGISTRY_DIR}"
        )
    return max(candidates, key=lambda d: d.get("templateVersion", 1))


def validate_template(doc: dict) -> list[str]:
    """Schema + citation + recipe-existence problems for one document."""
    validator = jsonschema.Draft202012Validator(_load_schema())
    problems = [
        f"{doc.get('templateId', '?')}: "
        + ".".join(str(p) for p in err.absolute_path)
        + f": {err.message}"
        for err in sorted(
            validator.iter_errors(doc), key=lambda e: list(e.absolute_path)
        )
    ]
    if problems:
        return problems
    tid = doc["templateId"]
    known = _recipe_catalogue()
    for entry in doc["protocolSkeleton"].get("analysisPlan", []):
        for recipe_id in entry.get("recipes", []):
            if recipe_id not in known:
                problems.append(
                    f"{tid}: analysisPlan names recipe {recipe_id!r} which "
                    f"does not exist in the analysis catalogue (F2.3: a "
                    f"template cannot promise an analysis the platform "
                    f"can't run)"
                )
    # Every {{ placeholder }} in the skeleton must be a declared parameter,
    # else the template passes validation but cannot instantiate (F1.1: a
    # template *instantiates* into a valid protocol — validation must
    # guarantee that, not just schema-shape).
    declared = set(doc.get("parameters", {}))
    used = _skeleton_placeholders(doc.get("protocolSkeleton", {}))
    for name in sorted(used - declared):
        problems.append(
            f"{tid}: protocolSkeleton uses {{{{ {name} }}}} but no parameter "
            f"{name!r} is declared — the template could not instantiate"
        )
    return problems


def _skeleton_placeholders(node: Any) -> set[str]:
    """Every ``{{ name }}`` referenced anywhere in the skeleton."""
    found: set[str] = set()
    if isinstance(node, str):
        found.update(_EMBEDDED_PLACEHOLDER.findall(node))
    elif isinstance(node, list):
        for item in node:
            found |= _skeleton_placeholders(item)
    elif isinstance(node, dict):
        for value in node.values():
            found |= _skeleton_placeholders(value)
    return found


def _recipe_catalogue() -> frozenset[str]:
    """Recipe ids the platform can actually run (FR-ANA-2). The analysis
    package is a workspace sibling; if it cannot import, the check fails
    loudly rather than passing silently."""
    try:
        import analysis.recipes  # noqa: F401 - registers recipes on import
        from analysis.core import REGISTRY
    except ImportError as exc:  # pragma: no cover - broken install only
        raise TemplateError(
            f"analysis recipe catalogue unavailable ({exc}); cannot verify "
            "template statistical plans"
        ) from exc
    return frozenset(REGISTRY.keys())


def validate_registry() -> list[str]:
    """All problems across the registry ([] = every template valid)."""
    problems = []
    seen: set[tuple[str, int]] = set()
    for path, doc in _read_all():
        problems.extend(validate_template(doc))
        key = (doc.get("templateId", path.stem), doc.get("templateVersion", 1))
        if key in seen:
            problems.append(f"{path.name}: duplicate templateId@templateVersion {key}")
        seen.add(key)
    return problems


def list_templates() -> list[dict]:
    """Latest version of every template, with the metadata both surfaces
    (conversation cards and the FR-TPL-3 form) render."""
    latest: dict[str, dict] = {}
    for _, doc in _read_all():
        tid = doc.get("templateId", "")
        if not tid:
            continue
        if tid not in latest or doc.get("templateVersion", 1) > latest[tid].get(
            "templateVersion", 1
        ):
            latest[tid] = doc
    return [
        {
            "templateId": doc["templateId"],
            "templateVersion": doc.get("templateVersion", 1),
            "title": doc.get("title", ""),
            "description": doc.get("description", ""),
            "designType": doc.get("designType", ""),
            "dataPath": doc.get("dataPath", ""),
            "source": doc.get("source", []),
            "parameters": doc.get("parameters", {}),
            "measures": doc.get("measures", []),
            "statisticalPlan": doc.get("statisticalPlan", {}),
            "threats": doc.get("threats", []),
        }
        for _, doc in sorted(
            ((tid, d) for tid, d in latest.items()), key=lambda x: x[0]
        )
    ]


# ------------------------------------------------------------ parameters


def _coerce(name: str, definition: dict, value: Any) -> Any:
    """Type-check and coerce one supplied parameter value."""
    kind = definition.get("type", "string")
    try:
        if kind in ("int", "participants"):
            value = int(value)
        elif kind == "float":
            value = float(value)
        elif kind == "bool":
            if isinstance(value, str):
                value = value.lower() in ("true", "1", "yes")
            value = bool(value)
        elif kind == "conditions":
            if not (
                isinstance(value, list)
                and value
                and all(isinstance(c, str) and c for c in value)
            ):
                raise ValueError("must be a non-empty list of names")
            return value
        else:
            value = str(value)
    except (TypeError, ValueError) as exc:
        raise TemplateError(f"parameter {name!r}: {exc}") from exc
    minimum, maximum = definition.get("min"), definition.get("max")
    if minimum is not None and isinstance(value, (int, float)) and value < minimum:
        raise TemplateError(f"parameter {name!r}: {value} is below min {minimum}")
    if maximum is not None and isinstance(value, (int, float)) and value > maximum:
        raise TemplateError(f"parameter {name!r}: {value} is above max {maximum}")
    allowed = definition.get("enum")
    if allowed and value not in allowed:
        raise TemplateError(f"parameter {name!r}: {value!r} not one of {allowed}")
    if kind == "string" and len(str(value)) < definition.get("minLength", 0):
        raise TemplateError(f"parameter {name!r}: shorter than minLength")
    return value


def resolve_parameters(template: dict, supplied: dict) -> dict:
    """Defaults + supplied values, typed and bounds-checked. Unknown names
    and missing no-default parameters fail loudly (F1.3 posture: named
    gaps, never silent ones)."""
    definitions = template.get("parameters", {})
    unknown = sorted(set(supplied) - set(definitions))
    if unknown:
        raise TemplateError(
            f"unknown parameter(s) {', '.join(unknown)} for {template['templateId']}"
        )
    resolved = {}
    missing = []
    for name, definition in definitions.items():
        if name in supplied:
            resolved[name] = _coerce(name, definition, supplied[name])
        elif "default" in definition:
            resolved[name] = definition["default"]
        else:
            missing.append(name)
    if missing:
        raise TemplateError(f"missing required parameter(s): {', '.join(missing)}")
    return resolved


def _fill(node: Any, values: dict) -> Any:
    """Recursively fill placeholders; exact placeholders keep the value's
    type. Any placeholder left unfilled is an error, not a silent gap."""
    if isinstance(node, str):
        exact = _EXACT_PLACEHOLDER.match(node)
        if exact:
            name = exact.group(1)
            if name not in values:
                raise TemplateError(f"unfilled placeholder {{{{ {name} }}}}")
            return values[name]

        def _sub(match: re.Match) -> str:
            name = match.group(1)
            if name not in values:
                raise TemplateError(f"unfilled placeholder {{{{ {name} }}}}")
            return str(values[name])

        return _EMBEDDED_PLACEHOLDER.sub(_sub, node)
    if isinstance(node, list):
        return [_fill(item, values) for item in node]
    if isinstance(node, dict):
        return {key: _fill(value, values) for key, value in node.items()}
    return node


def instantiate_template(
    template_id: str, parameters: dict, *, version: int | None = None
) -> dict:
    """Template + parameters → validated protocol dict (FR-TPL-1.4).

    Returns ``{protocol, templateId, templateVersion, parameters}``; raises
    :class:`TemplateError` when the template is invalid, a parameter is
    missing/out-of-bounds, or the filled protocol fails validation - a
    template instantiation can never silently produce an invalid draft
    (same posture as FR-CONV-3.2).
    """
    from protocol.loader import validate_protocol

    template = load_template(template_id, version)
    problems = validate_template(template)
    if problems:
        raise TemplateError("; ".join(problems))
    values = resolve_parameters(template, parameters)
    protocol = _fill(template["protocolSkeleton"], values)
    errors = validate_protocol(protocol)
    if errors:
        raise TemplateError(
            f"{template_id} instantiation is not a valid protocol: " + "; ".join(errors)
        )
    return {
        "protocol": protocol,
        "templateId": template["templateId"],
        "templateVersion": template.get("templateVersion", 1),
        "parameters": values,
    }


# ------------------------------------------------------- plan explainer


def explain_plan(template: dict) -> list[str]:
    """The FR-TPL-2.3 plan explainer: each statistical choice in plain
    language with its why - never a bare test name (NFR-11 tone)."""
    plan = template.get("statisticalPlan", {})
    lines = [
        f"Analysis is per-{plan.get('unit', 'participant')} first - "
        "aggregating within the unit before comparing guards against "
        "pseudo-replication."
    ]
    for entry in plan.get("perRQ", []):
        framing = entry.get("smallN", "hypothesis-generating")
        lines.append(
            f"{entry.get('rq', '?')}: the outcome is {entry.get('outcome')}, "
            f"so the prescribed test is {entry.get('test')} with "
            f"{entry.get('effectSize')} as its effect size; at small n the "
            f"result is framed as {framing}, and never reported as a bare "
            "p-value."
        )
    for threat in template.get("threats", []):
        cite = f" (see {threat['cite']})" if threat.get("cite") else ""
        lines.append(
            f"Known threat - {threat.get('threat')}: mitigated by "
            f"{threat.get('mitigation')}{cite}."
        )
    return lines
