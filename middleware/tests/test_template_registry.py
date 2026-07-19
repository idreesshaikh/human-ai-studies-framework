"""Template registry tests.

F1.1 (every registry template validates and instantiates into a protocol
that passes validation, zero hand edits), F2.3 (a template naming a
nonexistent recipe fails registry validation — earlier than instantiation),
and typed-parameter handling.
"""

import pytest
from protocol.loader import validate_protocol

from middleware import template_registry as tr


def test_registry_is_valid():
    """F2.3 (and the registry invariant): the shipped registry has no
    problems — schema, mandatory citations, every recipe exists, every
    skeleton placeholder is a declared parameter."""
    assert tr.validate_registry() == []


def test_every_template_instantiates_to_a_valid_protocol():
    """F1.1: each registry template instantiates (with defaults) into a
    protocol that passes protocol validation with zero hand edits."""
    templates = tr.list_templates()
    assert templates, "the registry must ship seed templates"
    for meta in templates:
        result = tr.instantiate_template(meta["templateId"], {})
        assert validate_protocol(result["protocol"]) == [], meta["templateId"]


def test_nonexistent_recipe_fails_validation():
    """F2.3: a template promising a recipe the platform can't run is caught
    at registry validation, before anyone instantiates it."""
    doc = tr.load_template("metr-rct-v1")
    doc = {
        **doc,
        "protocolSkeleton": {
            **doc["protocolSkeleton"],
            "analysisPlan": [{"rq": "RQ-1", "recipes": ["no-such-recipe"]}],
        },
    }
    problems = tr.validate_template(doc)
    assert any("no-such-recipe" in p for p in problems)


def test_parameter_bounds_are_enforced():
    """A supplied parameter below its declared minimum is refused with a
    named error, not silently clamped."""
    with pytest.raises(tr.TemplateError):
        tr.instantiate_template("metr-rct-v1", {"participantPlan": 0})


def test_unknown_parameter_is_refused():
    with pytest.raises(tr.TemplateError):
        tr.instantiate_template("metr-rct-v1", {"notAParam": 3})


def test_versioning_records_which_version_produced_the_draft():
    """F1.3 (templates): instantiation records the template id + version."""
    result = tr.instantiate_template("metr-rct-v1", {})
    assert result["templateId"] == "metr-rct-v1"
    assert result["templateVersion"] >= 1
