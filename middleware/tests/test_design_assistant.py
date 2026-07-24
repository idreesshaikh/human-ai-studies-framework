"""Unit tests for design_assistant.recommend_templates (FR-CONV-1.4) and the
near-duplicate move guard (``_filter_repeated_moves``).

Regression coverage for a real production gap: an open-ended or loosely
worded design ask produced zero template candidates, so the LLM (which may
only ever choose a template from what this function retrieves) could never
propose a ``choose-template`` move - and since the protocol's ``design``
section can *only* be filled by that move kind (design_llm.py), the
researcher could never reach a compilable protocol no matter how many other
moves they accepted.
"""

from middleware.design_assistant import (
    ScriptedMove,
    _filter_repeated_moves,
    _is_near_duplicate,
    recommend_templates,
)


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


# ------------------------------------------- near-duplicate guard (FR-CONV)


def _mv(kind: str, proposal: str, patch: dict | None = None) -> ScriptedMove:
    return ScriptedMove(
        kind=kind, target="protocol", proposal=proposal, patch=patch, refs=()
    )


def _state(key_texts=(), template_ids=(), advisory_texts=()) -> dict:
    return {
        "accepted": [],
        "rejected": [],
        "proposed": [],
        "filled": [],
        "empty": [],
        "templateId": None,
        "templateIds": list(template_ids),
        "keyTexts": list(key_texts),
        "advisoryTexts": list(advisory_texts),
    }


def test_near_duplicate_catches_exact_and_paraphrase():
    prior = (
        "Measure review latency — the time a suggestion stays visible "
        "before accept/reject."
    )
    assert _is_near_duplicate(prior, prior)
    assert _is_near_duplicate(
        "Measure review latency (time before accept).", prior
    )
    moves = (_mv("add-measure", "Measure review latency (time before accept)."),)
    assert _filter_repeated_moves(moves, _state(key_texts=[prior])) == ()


def test_distinct_moves_survive_the_filter():
    prior = "Measure review latency (time before accept)."
    move = _mv(
        "set-parameter",
        "Recruit 24 professional developers as participants.",
        {"section": "participants", "op": "set", "value": "24 professionals"},
    )
    assert _filter_repeated_moves((move,), _state(key_texts=[prior])) == (move,)


def test_choose_template_duplicate_is_keyed_on_template_id():
    """A re-pitched template is repetition however it's re-worded — and a
    template the conversation has never seen is not."""
    state = _state(template_ids=["metr-rct-v1"])
    repeat = _mv(
        "choose-template",
        "How about a paired RCT, as in the METR study?",
        {"templateId": "metr-rct-v1", "parameters": {}},
    )
    fresh = _mv(
        "choose-template",
        "A two-group RCT could fit better.",
        {"templateId": "two-group-rct-v1", "parameters": {}},
    )
    assert _filter_repeated_moves((repeat, fresh), state) == (fresh,)


def test_filter_is_a_no_op_without_state():
    """The stateless demo path (no study, no stored moves) is untouched."""
    moves = (_mv("add-measure", "Measure review latency."),)
    assert _filter_repeated_moves(moves, None) is moves


def test_caution_never_blocks_the_section_move_that_addresses_it():
    """Regression: an accepted ethics caution's wording must not stop the
    ethics posture from ever being proposed — the section move that
    addresses a caution naturally restates it, and cautions fill nothing."""
    caution = "Workspace snapshots may include personal or sensitive data."
    move = _mv(
        "set-parameter",
        "Add an ethics posture: workspace snapshots may include personal "
        "data, so consent must cover snapshot content.",
        {
            "section": "ethics",
            "op": "append",
            "value": "Consent covers snapshot content; personal data included",
        },
    )
    state = _state(advisory_texts=[caution])
    assert _filter_repeated_moves((move,), state) == (move,)


def test_a_repeated_caution_is_still_dropped():
    """Caution-vs-caution (and caution-vs-content) repetition stays
    suppressed — only the advisory→content direction is exempt."""
    caution = "Workspace snapshots may include personal or sensitive data."
    echo = _mv(
        "caution",
        "Careful: workspace snapshots may include personal or sensitive data.",
    )
    assert _filter_repeated_moves((echo,), _state(advisory_texts=[caution])) == ()
    content_echo = _mv("caution", "Measure review latency (time before accept).")
    state = _state(key_texts=["Measure review latency (time before accept)."])
    assert _filter_repeated_moves((content_echo,), state) == ()
