"""Unit tests for design_assistant.recommend_templates (FR-CONV-1.4).

Regression coverage for a real production gap: an open-ended or loosely
worded design ask produced zero template candidates, so the LLM (which may
only ever choose a template from what this function retrieves) could never
propose a ``choose-template`` move - and since the protocol's ``design``
section can *only* be filled by that move kind (design_llm.py), the
researcher could never reach a compilable protocol no matter how many other
moves they accepted.
"""

from middleware.design_assistant import recommend_templates


def test_generic_design_ask_falls_back_to_the_full_catalog():
    """No template's specific jargon is present, but the ask is clearly
    about design - the LLM must still get candidates to choose from."""
    templates = recommend_templates("help me get started on the design")
    assert templates, "a design-related ask must never yield zero candidates"


def test_rct_phrasing_matches_the_rct_template():
    """The exact wording researchers actually use ('random control trial(s)'
    is a common non-technical phrasing of RCT) must resolve to the RCT
    template, not just the unscored fallback catalog."""
    templates = recommend_templates("I want to do random control trials as design")
    assert templates[0]["templateId"] == "two-group-rct-v1"
    assert "Matched" in templates[0]["matchReason"]
