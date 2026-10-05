"""
Unit tests for design_assistant.recommend_templates (FR-CONV-1.4) and the near-duplicate
move guard (``_filter_repeated_moves``).
"""

from middleware.design_assistant import (
    ProposedMove,
    _facet_settled_in_state,
    _filter_repeated_moves,
    _guard_completion_claim,
    _is_near_duplicate,
    recommend_templates,
)


def test_generic_design_ask_falls_back_to_the_full_catalog():
    """
    No template's specific jargon is present, but the ask is clearly about design - the
    LLM must still get candidates to choose from.
    """
    templates = recommend_templates("help me get started on the design")
    assert templates, "a design-related ask must never yield zero candidates"


def test_rct_phrasing_matches_the_rct_template():
    """
    The exact wording researchers actually use ('random control trial(s)' is a common
    non-technical phrasing of RCT) must resolve to the RCT template, not just the
    unscored fallback catalog.
    """
    templates = recommend_templates("I want to do random control trials as design")
    assert templates[0]["templateId"] == "two-group-rct-v1"
    assert "Matched" in templates[0]["matchReason"]


def _mv(kind: str, proposal: str, patch: dict | None = None) -> ProposedMove:
    return ProposedMove(
        kind=kind, target="protocol", proposal=proposal, patch=patch, refs=()
    )


def _state(key_texts=(), template_ids=(), advisory_texts=(), merge_keys=()) -> dict:
    return {
        "accepted": [],
        "rejected": [],
        "proposed": [],
        "filled": [],
        "empty": [],
        "templateId": None,
        "templateIds": list(template_ids),
        "mergeKeys": list(merge_keys),
        "keyTexts": list(key_texts),
        "advisoryTexts": list(advisory_texts),
    }


def test_near_duplicate_catches_exact_and_paraphrase():
    prior = (
        "Measure review latency  -  the time a suggestion stays visible "
        "before accept/reject."
    )
    assert _is_near_duplicate(prior, prior)
    assert _is_near_duplicate("Measure review latency (time before accept).", prior)
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
    """
    A re-pitched template is repetition however it's re-worded  -  and a template the
    conversation has never seen is not.
    """
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


def test_merge_duplicate_is_keyed_on_the_id_set():
    """
    The same pair of shapes is the same merge however it's re-worded; a genuinely
    different combination is not repetition.
    """
    state = _state(merge_keys=["metr-rct-v1+survey-self-report-v1"])
    repeat = _mv(
        "merge-templates",
        "Pair the telemetry shape with the survey for perception data.",
        {"templateIds": ["survey-self-report-v1", "metr-rct-v1"], "reason": "x"},
    )
    fresh = _mv(
        "merge-templates",
        "Combine the telemetry shape with the multi-arm RCT instead.",
        {"templateIds": ["metr-rct-v1", "multi-arm-rct-v1"], "reason": "y"},
    )
    kept = _filter_repeated_moves((repeat, fresh), state)
    assert kept == (fresh,)


def test_filter_is_a_no_op_without_state():
    """The stateless demo path (no study, no stored moves) is untouched."""
    moves = (_mv("add-measure", "Measure review latency."),)
    assert _filter_repeated_moves(moves, None) is moves


def test_completion_claim_is_reconciled_with_open_protocol_slots():
    state = {
        "outstandingSlots": [{"label": "the conditions"}],
        "compileValid": False,
        "compileErrors": [],
    }
    text = _guard_completion_claim(
        "The protocol is complete. It will compile as-is.", state
    )
    assert text == "The draft is not complete yet. Still open: the conditions."


def test_settled_compiled_facets_are_not_asked_again():
    state = {
        "filled": ["participants", "conditions", "measures"],
        "outstandingSlots": [],
        "taskDescription": True,
        "sessionMinutes": 45,
    }
    assert _facet_settled_in_state("population", state)
    assert _facet_settled_in_state("task", state)
    assert _facet_settled_in_state("comparison", state)
    assert _facet_settled_in_state("outcome", state)
    assert _facet_settled_in_state("constraints", state)


def test_caution_never_blocks_the_section_move_that_addresses_it():
    """
    Regression: an accepted ethics caution's wording must not stop the ethics posture
    from ever being proposed  -  the section move that addresses a caution naturally
    restates it, and cautions fill nothing.
    """
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
    """
    Caution-vs-caution (and caution-vs-content) repetition stays suppressed  -  only the
    advisory→content direction is exempt.
    """
    caution = "Workspace snapshots may include personal or sensitive data."
    echo = _mv(
        "caution",
        "Careful: workspace snapshots may include personal or sensitive data.",
    )
    assert _filter_repeated_moves((echo,), _state(advisory_texts=[caution])) == ()
    content_echo = _mv("caution", "Measure review latency (time before accept).")
    state = _state(key_texts=["Measure review latency (time before accept)."])
    assert _filter_repeated_moves((content_echo,), state) == ()


def _duration_move():
    return ProposedMove(
        "set-field",
        "session.durationMinutes",
        "Sessions run 30 minutes.",
        {"op": "set-field", "path": ["session", "durationMinutes"], "value": 30},
        (),
    )


def test_explicit_turn_names_what_was_recorded_and_asks_the_next_question():
    from middleware.design_assistant import _explicit_turn

    move = _duration_move()
    stance = {
        "explicitMoves": (move,),
        "nextQuestion": "How many participants can you recruit?",
    }
    state = {"keyTexts": ["Sessions run 30 minutes. 30"]}
    turn = _explicit_turn(stance, state)
    assert turn is not None and turn.moves == ()
    assert "already have those details recorded" not in turn.text
    assert "Sessions run 30 minutes." in turn.text
    assert turn.text.rstrip().endswith("How many participants can you recruit?")


def test_explicit_turn_without_a_next_question_still_asks_something():
    from middleware.design_assistant import _explicit_turn

    stance = {"explicitMoves": (_duration_move(),), "nextQuestion": ""}
    state = {"keyTexts": ["Sessions run 30 minutes. 30"]}
    turn = _explicit_turn(stance, state)
    assert "Sessions run 30 minutes." in turn.text
    assert turn.text.rstrip().endswith("?")


def test_scaffolding_turn_asks_the_open_slot_question_not_just_names_it():
    from middleware.design_assistant import _scaffolding_turn

    stance = {"understanding": {"known": True, "missing": []}}
    state = {
        "outstandingSlots": [
            {
                "key": "participants.planned",
                "label": "how many participants",
                "question": "How many participants can you realistically recruit?",
            }
        ],
        "compileValid": True,
    }
    turn = _scaffolding_turn(stance, [], state)
    assert "I already have" not in turn.text
    assert "How many participants can you realistically recruit?" in turn.text


# --- revisions of an already-stated number are not repeats ---------------------------


def _numeric_key(proposal: str, value: int) -> str:
    from middleware.design_assistant import _move_key_text

    return _move_key_text(proposal, {"value": value})


def test_moves_differing_only_in_a_number_are_not_near_duplicates():
    assert not _is_near_duplicate(
        _numeric_key("Run each session for 30 minutes", 30),
        _numeric_key("Run each session for 45 minutes", 45),
    )
    assert not _is_near_duplicate(
        _numeric_key("Plan for 12 participants", 12),
        _numeric_key("Plan for 16 participants", 16),
    )
    # The same number is still a repeat.
    assert _is_near_duplicate(
        _numeric_key("Run each session for 30 minutes", 30),
        _numeric_key("Run each session for 30 minutes", 30),
    )


def test_a_revision_of_an_accepted_number_is_kept_as_a_card():
    prior = _numeric_key("Run each session for 30 minutes.", 30)
    revision = _mv(
        "set-field",
        "Run each session for 45 minutes.",
        {"op": "set-field", "path": ["session", "durationMinutes"], "value": 45},
    )
    assert _filter_repeated_moves((revision,), _state(key_texts=[prior])) == (revision,)


def test_explicit_revision_is_proposed_not_claimed_as_already_in_draft():
    from middleware.design_assistant import _explicit_turn

    revision = _mv(
        "set-field",
        "Run each session for 45 minutes.",
        {"op": "set-field", "path": ["session", "durationMinutes"], "value": 45},
    )
    state = {"keyTexts": [_numeric_key("Run each session for 30 minutes.", 30)]}
    turn = _explicit_turn({"explicitMoves": (revision,)}, state)
    assert turn is not None and turn.moves == (revision,)
    assert "already in the draft" not in turn.text


def test_change_participants_request_still_yields_a_card_once_the_draft_is_valid():
    from middleware.design_assistant import _explicit_moves, _explicit_turn

    moves = _explicit_moves("change participants to 20")
    assert [m.patch["path"] for m in moves] == [["participants", "planned"]]
    assert moves[0].patch["value"] == 20
    state = {
        "compileValid": True,
        "keyTexts": [_numeric_key("Plan for 12 participants.", 12)],
    }
    turn = _explicit_turn({"explicitMoves": moves, "nextQuestion": ""}, state)
    assert turn is not None and len(turn.moves) == 1
    assert "every required decision" not in turn.text
    assert "already in the draft" not in turn.text
