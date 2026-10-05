"""Template registry tests."""

import pytest
from protocol.loader import validate_protocol

from middleware import template_registry as tr


def test_registry_is_valid():
    """
    F2.3 (and the registry invariant): the shipped registry has no problems  -  schema,
    mandatory citations, every recipe exists, every skeleton placeholder is a declared
    parameter.
    """
    assert tr.validate_registry() == []


def test_every_template_instantiates_to_a_valid_protocol():
    """
    F1.1: each registry template instantiates (with defaults) into a protocol that
    passes protocol validation with zero hand edits.
    """
    templates = tr.list_templates()
    assert templates, "the registry must ship seed templates"
    for meta in templates:
        result = tr.instantiate_template(meta["templateId"], {})
        assert validate_protocol(result["protocol"]) == [], meta["templateId"]


def test_nonexistent_recipe_fails_validation():
    """
    F2.3: a template promising a recipe the platform can't run is caught at registry
    validation, before anyone instantiates it.
    """
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
    """
    A supplied parameter below its declared minimum is refused with a named error, not
    silently clamped.
    """
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


def test_a_filled_protocol_that_still_fails_validation_reports_plain_field_names(
    monkeypatch,
):
    """
    Rare path: an LLM-supplied parameter passes its own type/bounds check yet the filled
    protocol still fails schema validation (every registry template's own DEFAULTS are
    covered by test_registry_is_valid, so this can only happen with a supplied value).
    """
    raw_errors = [
        "analysisPlan: [] should be non-empty",
        "instruments: {} is not valid under any of the given schemas",
        "study.ethicsRef: '' should be non-empty",
    ]
    monkeypatch.setattr(
        "protocol.loader.validate_protocol", lambda protocol: raw_errors
    )
    with pytest.raises(tr.TemplateError) as excinfo:
        tr.instantiate_template("metr-rct-v1", {})
    message = str(excinfo.value)
    for jargon in (
        "should be non-empty",
        "is not valid under any of the given schemas",
        "given schemas",
    ):
        assert jargon not in message, message
    for field in ("analysisPlan", "instruments", "study.ethicsRef"):
        assert field in message, message


def test_template_text_shown_to_researchers_has_no_internal_wording():
    """Titles and descriptions are read by researchers: no build phases, no raw
    template ids, no broken hyphenation."""
    import re

    bad = []
    for path, doc in tr._read_all():
        for field in ("title", "description"):
            text = " ".join(str(doc.get(field, "")).split())
            if re.search(r"\b(phase|wave)\s*\d", text, re.I):
                bad.append(f"{path.name} {field}: names a build phase")
            if re.search(r"\b[a-z0-9]+(?:-[a-z0-9]+)*-v\d+\b", text):
                bad.append(f"{path.name} {field}: shows a raw template id")
            if re.search(r"\w- \w", text):
                bad.append(f"{path.name} {field}: stray hyphen break")
            if "`" in text or "**" in text:
                bad.append(f"{path.name} {field}: shows raw markdown")
    assert not bad, bad
