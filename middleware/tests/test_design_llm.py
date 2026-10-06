"""Unit tests for the LLM-driven design-conversation seam (FR-CONV-1.4)."""

import json

from middleware import assistant, design_llm

PAPERS = [
    {"ref": "corpus:trust-in-ai-code-generation", "title": "Trust in AI Code"},
    {"ref": "corpus:metr-early-2025-dev-productivity", "title": "METR Productivity"},
]
TEMPLATES = [
    {"templateId": "metr-rct-v1", "title": "METR RCT", "designShape": "paired"},
    {"templateId": "survey-self-report-v1", "title": "Survey", "designShape": "paired"},
]


def _fake_client(content: str | dict, raises: Exception | None = None):
    def post(url, body, headers):
        if raises is not None:
            raise raises
        payload = content if isinstance(content, str) else json.dumps(content)
        return {"choices": [{"message": {"content": payload}}]}

    return assistant.MistralProvider("test-key", post=post)


def test_propose_turn_happy_path_returns_validated_moves():
    reply = {
        "text": "Here's a grounded move for that.",
        "moves": [
            {
                "kind": "add-measure",
                "target": "measures[]",
                "proposal": "Measure review latency.",
                "patch": {
                    "section": "measures",
                    "op": "append",
                    "value": "Review latency",
                },
                "refs": ["corpus:trust-in-ai-code-generation"],
            }
        ],
    }
    client = _fake_client(reply)
    script = design_llm.propose_turn(client, "over-trust", [], PAPERS, TEMPLATES)
    assert script is not None
    assert script.text == "Here's a grounded move for that."
    assert len(script.moves) == 1
    assert script.moves[0].kind == "add-measure"
    assert script.moves[0].refs == ("corpus:trust-in-ai-code-generation",)


def test_propose_turn_strips_refs_outside_the_candidate_menu():
    """
    Wall #3: a citation the model invents (not in the menu this turn) never survives,
    even though the JSON is otherwise well-formed.
    """
    reply = {
        "text": "Reply.",
        "moves": [
            {
                "kind": "caution",
                "target": "measures",
                "proposal": "A caution.",
                "patch": None,
                "refs": ["corpus:not-actually-retrieved"],
            }
        ],
    }
    client = _fake_client(reply)
    script = design_llm.propose_turn(client, "text", [], PAPERS, TEMPLATES)
    assert script is not None
    assert script.moves[0].refs == ()


def test_propose_turn_drops_unknown_kind_but_keeps_the_text():
    reply = {
        "text": "Still a useful reply.",
        "moves": [
            {
                "kind": "delete-everything",
                "target": "x",
                "proposal": "not a real kind",
                "patch": None,
                "refs": [],
            }
        ],
    }
    client = _fake_client(reply)
    script = design_llm.propose_turn(client, "text", [], PAPERS, TEMPLATES)
    assert script is not None
    assert script.text == "Still a useful reply."
    assert script.moves == ()


def test_propose_turn_drops_a_move_whose_patch_never_validates():
    """
    Regression: a non-caution move whose patch fails validation used to render anyway
    with `patch=None` - accepting it looked like it worked but silently never touched
    the draft (the "accepted but only noted" trap previously guarded only for
    choose-template).
    """
    reply = {
        "text": "Reply.",
        "moves": [
            {
                "kind": "add-measure",
                "target": "measures[]",
                "proposal": "A move with a garbage patch.",
                "patch": {"section": "not-a-real-section", "op": "append", "value": 1},
                "refs": [],
            }
        ],
    }
    client = _fake_client(reply)
    script = design_llm.propose_turn(client, "text", [], PAPERS, TEMPLATES)
    assert script is not None
    assert script.moves == ()


def test_add_instrument_kind_naming_the_ethics_section_is_salvaged():
    """Regression: an observed real-world failure."""
    reply = {
        "text": "Here's an ethics posture.",
        "moves": [
            {
                "kind": "add-instrument",
                "target": "ethics",
                "proposal": "Adopt an ethics posture requiring informed "
                "consent, full data anonymization, and the right to "
                "withdraw at any time without penalty.",
                "patch": {
                    "section": "ethics",
                    "op": "append",
                    "value": "Informed consent, full anonymization, "
                    "withdrawal at any time without penalty",
                },
                "refs": [],
            }
        ],
    }
    client = _fake_client(reply)
    script = design_llm.propose_turn(
        client, "give me ethics posture", [], PAPERS, TEMPLATES
    )
    assert script is not None
    assert len(script.moves) == 1
    assert script.moves[0].patch == {
        "section": "ethics",
        "op": "append",
        "value": "Informed consent, full anonymization, withdrawal at any "
        "time without penalty",
    }


def test_propose_turn_validates_choose_template_patch():
    reply = {
        "text": "Adopt the METR template.",
        "moves": [
            {
                "kind": "choose-template",
                "target": "design",
                "proposal": "Use the METR RCT template.",
                "patch": {"templateId": "metr-rct-v1"},
                "refs": ["metr-rct-v1"],
            }
        ],
    }
    client = _fake_client(reply)
    script = design_llm.propose_turn(client, "text", [], PAPERS, TEMPLATES)
    assert script is not None
    assert script.moves[0].patch == {"templateId": "metr-rct-v1", "parameters": {}}
    assert script.moves[0].refs == ("metr-rct-v1",)


def test_propose_turn_normalizes_list_and_numeric_patch_values():
    """
    Section values must end up as strings: a list survives (the compiler flattens it
    into one entry per item), a number is stringified, and a dict value drops - and
    therefore drops the whole move, rather than poisoning the draft's schema or offering
    a move that no-ops.
    """
    reply = {
        "text": "Reply.",
        "moves": [
            {
                "kind": "set-parameter",
                "target": "conditions",
                "proposal": "Two conditions.",
                "patch": {
                    "section": "conditions",
                    "op": "append",
                    "value": ["AI-assisted", "Traditional resources"],
                },
                "refs": [],
            },
            {
                "kind": "set-parameter",
                "target": "participants",
                "proposal": "Plan for 24 participants.",
                "patch": {"section": "participants", "op": "set", "value": 24},
                "refs": [],
            },
            {
                "kind": "set-parameter",
                "target": "ethics",
                "proposal": "A dict value.",
                "patch": {"section": "ethics", "op": "append", "value": {"a": 1}},
                "refs": [],
            },
        ],
    }
    client = _fake_client(reply)
    script = design_llm.propose_turn(client, "text", [], PAPERS, TEMPLATES)
    assert script is not None
    assert len(script.moves) == 2
    assert script.moves[0].patch["value"] == ["AI-assisted", "Traditional resources"]
    assert script.moves[1].patch["value"] == "24"


def test_propose_turn_drops_choose_template_with_hallucinated_id():
    """
    A choose-template move naming a template the registry doesn't have is dropped
    entirely  -  accepted, it would poison every future compile, and patch-less it would
    be the "accepted but only noted" trap.
    """
    reply = {
        "text": "Adopt a template.",
        "moves": [
            {
                "kind": "choose-template",
                "target": "design",
                "proposal": "Use a made-up template.",
                "patch": {"templateId": "hallucinated-rct-2026"},
                "refs": [],
            }
        ],
    }
    client = _fake_client(reply)
    script = design_llm.propose_turn(client, "text", [], PAPERS, TEMPLATES)
    assert script is not None
    assert script.text == "Adopt a template."
    assert script.moves == ()


def test_propose_turn_validates_merge_templates_patch():
    reply = {
        "text": "Merge those two shapes.",
        "moves": [
            {
                "kind": "merge-templates",
                "target": "design",
                "proposal": "Combine the METR RCT with the survey shape.",
                "patch": {
                    "templateIds": ["metr-rct-v1", "survey-self-report-v1"],
                    "reason": "Objective behaviour data plus self-report.",
                },
                "refs": ["metr-rct-v1", "survey-self-report-v1"],
            }
        ],
    }
    client = _fake_client(reply)
    script = design_llm.propose_turn(client, "text", [], PAPERS, TEMPLATES)
    assert script is not None
    assert len(script.moves) == 1
    assert script.moves[0].kind == "merge-templates"
    assert script.moves[0].patch == {
        "templateIds": ["metr-rct-v1", "survey-self-report-v1"],
        "reason": "Objective behaviour data plus self-report.",
    }
    assert script.moves[0].refs == ("metr-rct-v1", "survey-self-report-v1")


def test_propose_turn_drops_merge_with_a_hallucinated_template_id():
    """
    A merge naming even one template the registry doesn't have is dropped  -  a merged
    protocol built on a hallucinated id could never instantiate.
    """
    reply = {
        "text": "Merge those two shapes.",
        "moves": [
            {
                "kind": "merge-templates",
                "target": "design",
                "proposal": "Combine a real shape with a made-up one.",
                "patch": {
                    "templateIds": ["metr-rct-v1", "hallucinated-rct-2026"],
                    "reason": "Both are needed.",
                },
                "refs": ["metr-rct-v1"],
            }
        ],
    }
    client = _fake_client(reply)
    script = design_llm.propose_turn(client, "text", [], PAPERS, TEMPLATES)
    assert script is not None
    assert script.moves == ()


def test_propose_turn_drops_merge_with_fewer_than_two_templates():
    reply = {
        "text": "Merge those shapes.",
        "moves": [
            {
                "kind": "merge-templates",
                "target": "design",
                "proposal": "Merge a single shape.",
                "patch": {
                    "templateIds": ["metr-rct-v1"],
                    "reason": "One is enough.",
                },
                "refs": ["metr-rct-v1"],
            }
        ],
    }
    client = _fake_client(reply)
    script = design_llm.propose_turn(client, "text", [], PAPERS, TEMPLATES)
    assert script is not None
    assert script.moves == ()


def test_propose_turn_returns_none_on_malformed_json():
    client = _fake_client("not json at all")
    assert design_llm.propose_turn(client, "text", [], PAPERS, TEMPLATES) is None


def test_propose_turn_returns_none_on_provider_failure():
    client = _fake_client({}, raises=TimeoutError("network down"))
    assert design_llm.propose_turn(client, "text", [], PAPERS, TEMPLATES) is None


def test_propose_turn_returns_none_when_reply_is_empty():
    reply = {"text": "", "moves": []}
    client = _fake_client(reply)
    assert design_llm.propose_turn(client, "text", [], PAPERS, TEMPLATES) is None


def test_propose_turn_accepts_text_only_reply_with_no_moves():
    """
    A conversational reply with nothing (yet) to propose is not a failure  -  it's an
    honest turn.
    """
    reply = {"text": "Tell me more about your population first.", "moves": []}
    client = _fake_client(reply)
    script = design_llm.propose_turn(client, "text", [], PAPERS, TEMPLATES)
    assert script is not None
    assert script.moves == ()


# ------------------------------------------------ design state (repetition + coverage
# steering): the structured block the prose history can't carry.


def _capturing_client(content: dict, captured: list):
    """Like ``_fake_client`` but records every request body sent."""

    def post(url, body, headers):
        captured.append(body)
        return {"choices": [{"message": {"content": json.dumps(content)}}]}

    return assistant.MistralProvider("test-key", post=post)


DESIGN_STATE = {
    "accepted": [
        {
            "kind": "add-measure",
            "section": "measures",
            "proposal": "Measure review latency.",
        }
    ],
    "rejected": [
        {
            "kind": "set-parameter",
            "section": "conditions",
            "proposal": "Run a three-arm condition split.",
        }
    ],
    "proposed": [],
    "filled": ["researchQuestions", "measures"],
    "empty": ["participants", "statisticalPlan"],
    "outstandingSlots": [
        {
            "key": "participants.planned",
            "label": "how many participants",
            "question": "How many participants can you realistically recruit?",
            "valueType": "integer",
            "choices": [],
        }
    ],
    "templateId": None,
    "templateIds": [],
    "keyTexts": ["Measure review latency.", "Run a three-arm condition split."],
}


def test_propose_turn_threads_design_state_into_the_request():
    captured: list = []
    client = _capturing_client({"text": "Noted.", "moves": []}, captured)
    script = design_llm.propose_turn(
        client, "what next?", [], PAPERS, TEMPLATES, design_state=DESIGN_STATE
    )
    assert script is not None
    user = captured[0]["messages"][-1]["content"]
    assert "Design state so far:" in user
    assert "Measure review latency." in user
    assert "Run a three-arm condition split." in user
    assert "The protocol still has open required fields: how many participants" in user
    system = captured[0]["messages"][0]["content"]
    assert "NEVER re-propose" in system


def test_design_state_prompt_keeps_recent_moves_without_growing_unbounded():
    """Keep recent decisions while the server enforces the full state."""
    state = {
        **DESIGN_STATE,
        "accepted": [
            {
                "kind": "add-measure",
                "section": "measures",
                "proposal": f"Measure {n}.",
            }
            for n in range(12)
        ],
    }

    block = design_llm._design_state_block(state)

    assert "4 earlier move(s) omitted" in block
    assert "Measure 0." not in block
    assert "Measure 11." in block


def test_propose_turn_notes_the_accepted_templates_prescribed_statistics():
    captured: list = []
    client = _capturing_client({"text": "Noted.", "moves": []}, captured)
    state = {
        **DESIGN_STATE,
        "templateId": "metr-rct-v1",
        "empty": [],
        "outstandingSlots": [],
    }
    design_llm.propose_turn(
        client, "what next?", [], PAPERS, TEMPLATES, design_state=state
    )
    user = captured[0]["messages"][-1]["content"]
    assert "Template metr-rct-v1 is accepted and prescribes" in user
    assert "record or refine that prescription" in user
    # A template never closes the statisticalPlan section outright  -  the regression
    # that
    # made the assistant refuse statisticalPlan moves.
    assert "do not propose a standalone statisticalPlan move" not in user


def test_cautions_render_as_advisory_and_the_prompt_says_they_fill_nothing():
    """
    A caution carries no patch: it must not read as draft content in the state block,
    and the standing prompt must say how ethics actually gets filled (the bug: two
    accepted ethics cautions, ethics slot still dark).
    """
    captured: list = []
    client = _capturing_client({"text": "Noted.", "moves": []}, captured)
    state = {
        **DESIGN_STATE,
        "accepted": [
            {
                "kind": "caution",
                "section": "ethics",
                "proposal": "Snapshots may capture personal data.",
            }
        ],
    }
    design_llm.propose_turn(
        client, "what next?", [], PAPERS, TEMPLATES, design_state=state
    )
    user = captured[0]["messages"][-1]["content"]
    assert "caution [ethics] (advisory, fills no section):" in user
    assert "set-parameter` move" in design_llm.SYSTEM_PROMPT
    assert 'patch.section` "ethics"' in design_llm.SYSTEM_PROMPT


def test_propose_turn_without_design_state_omits_the_block():
    """
    Backward compatible: no state (stateless demo, first turn)  -  the request looks
    exactly like before.
    """
    captured: list = []
    client = _capturing_client({"text": "Noted.", "moves": []}, captured)
    design_llm.propose_turn(client, "what next?", [], PAPERS, TEMPLATES)
    assert all(
        "Design state so far" not in m["content"] for m in captured[0]["messages"]
    )


# ------------------------------------------------ reply hygiene: loops, caps, markup

LOOPED_PARAGRAPH = (
    "That sounds like a within-subjects comparison. How many participants can "
    "you realistically recruit?"
)


def test_trim_repeated_text_keeps_first_of_a_looped_paragraph():
    looped = "\n\n".join([LOOPED_PARAGRAPH] * 12)
    assert design_llm.trim_repeated_text(looped) == LOOPED_PARAGRAPH


def test_trim_repeated_text_keeps_first_of_a_looped_sentence_in_one_line():
    looped = "Good start. " + "Which tasks will people do in the session? " * 8
    assert design_llm.trim_repeated_text(looped.strip()) == (
        "Good start. Which tasks will people do in the session?"
    )


def test_trim_repeated_text_leaves_clean_text_alone():
    clean = "Yes. No. Yes.\n\nSecond paragraph, different."
    assert design_llm.trim_repeated_text(clean) == clean


def test_cap_reply_text_cuts_at_a_sentence_boundary():
    long = "A sentence of moderate length here. " * 100
    capped = design_llm.cap_reply_text(long, limit=200)
    assert len(capped) <= 200
    assert capped.endswith(".")


def test_sanitize_reply_text_strips_markdown_and_names_templates():
    titles = {"metr-rct-v1": "METR RCT"}
    text = "Try **the METR design** (`metr-rct-v1`) with *care*, see metr-rct-v1."
    out = design_llm.sanitize_reply_text(text, titles)
    assert out == "Try the METR design (METR RCT) with care, see METR RCT."


def test_sanitize_reply_text_leaves_citation_links_and_unknown_ids_intact():
    text = "See [the paper](https://arxiv.org/abs/2507.09089) and __other-v1__."
    out = design_llm.sanitize_reply_text(text, {})
    assert out == "See [the paper](https://arxiv.org/abs/2507.09089) and other-v1."


def test_propose_turn_trims_a_looped_reply_and_resolves_template_ids():
    reply = {
        "text": "\n\n".join(["Use **metr-rct-v1** here."] * 6),
        "moves": [],
    }
    client = _fake_client(reply)
    turn = design_llm.propose_turn(client, "t", [], PAPERS, TEMPLATES)
    assert turn.text == "Use METR RCT here."


def test_streaming_salvages_truncated_json_without_a_second_call():
    calls = {"post": 0}

    def post(url, body, headers):
        calls["post"] += 1
        return {"choices": [{"message": {"content": "{}"}}]}

    def stream(url, body, headers):
        yield '{"text": "Half a reply that got cut'

    client = assistant.MistralProvider("k", post=post, stream=stream)
    gen = design_llm.propose_turn_streaming(client, "t", [], PAPERS, TEMPLATES)
    try:
        while True:
            next(gen)
    except StopIteration as stop:
        turn = stop.value
    assert calls["post"] == 0
    assert turn is not None and turn.text == "Half a reply that got cut"


def test_design_requests_cap_tokens_and_the_transport_has_timeouts():
    import inspect

    src = inspect.getsource(assistant)
    assert "timeout=60" in src and "timeout=120" in src
    assert design_llm.MAX_TOKENS <= 1200


def test_system_prompt_forbids_markdown_and_raw_ids_in_reply_text():
    prompt = design_llm.SYSTEM_PROMPT
    assert "PLAIN TEXT" in prompt
    assert "never write template ids" in prompt


def test_proposal_text_is_sanitised_like_the_reply_prose():
    reply = {
        "text": "Here is a design.",
        "moves": [
            {
                "kind": "choose-template",
                "target": "design",
                "proposal": (
                    "Use the **metr-rct-v1** template (`metr-rct-v1`) to structure "
                    "the study design."
                ),
                "patch": {"templateId": "metr-rct-v1", "parameters": {}},
                "refs": [],
            }
        ],
    }
    turn = design_llm.propose_turn(_fake_client(reply), "t", [], PAPERS, TEMPLATES)
    move = turn.moves[0]
    assert "*" not in move.proposal and "`" not in move.proposal
    assert "metr-rct-v1" not in move.proposal
    assert "METR RCT" in move.proposal
    # The patch keeps the real id: only display text changes.
    assert move.patch["templateId"] == "metr-rct-v1"


def test_streaming_proposal_text_is_sanitised_too():
    reply = json.dumps(
        {
            "text": "ok",
            "moves": [
                {
                    "kind": "add-measure",
                    "target": "measures[]",
                    "proposal": "Measure **review latency** per `metr-rct-v1` run.",
                    "patch": {
                        "section": "measures",
                        "op": "append",
                        "value": "Review latency",
                    },
                }
            ],
        }
    )

    def stream(url, body, headers):
        yield reply

    client = assistant.MistralProvider("k", post=lambda *a: {}, stream=stream)
    gen = design_llm.propose_turn_streaming(client, "t", [], PAPERS, TEMPLATES)
    try:
        while True:
            next(gen)
    except StopIteration as stop:
        turn = stop.value
    assert turn.moves[0].proposal == "Measure review latency per METR RCT run."


def _set_field_reply(path: list[str], value) -> dict:
    return {
        "text": "Reply.",
        "moves": [
            {
                "kind": "set-field",
                "target": ".".join(path),
                "proposal": "Plan for twelve participants.",
                "patch": {"op": "set-field", "path": path, "value": value},
                "refs": [],
            }
        ],
    }


def test_sample_size_aliases_are_mapped_to_the_planned_participants_slot():
    for alias in (["participants", "sampleSize"], ["participants", "size"], ["n"]):
        client = _fake_client(_set_field_reply(alias, 12))
        script = design_llm.propose_turn(client, "x", [], PAPERS, TEMPLATES)
        assert script.moves[0].patch["path"] == ["participants", "planned"], alias


def test_set_field_moves_for_non_fillable_slots_never_become_cards(caplog):
    client = _fake_client(_set_field_reply(["participants", "favouriteColour"], "red"))
    with caplog.at_level("INFO", logger="middleware.design_llm"):
        script = design_llm.propose_turn(client, "x", [], PAPERS, TEMPLATES)
    assert script.moves == ()
    assert "favouriteColour" in caplog.text


def test_system_prompt_lists_only_the_fillable_slot_names():
    from middleware import compiler

    for key in compiler.FILLABLE_SLOTS:
        assert f"`{key}`" in design_llm.SYSTEM_PROMPT
    assert "sampleSize" not in design_llm.SYSTEM_PROMPT


def test_a_stray_comparison_template_parameter_is_dropped_at_parse_time():
    reply = {
        "text": "Reply.",
        "moves": [
            {
                "kind": "choose-template",
                "target": "design",
                "proposal": "Use the METR design.",
                "patch": {
                    "templateId": "metr-rct-v1",
                    "parameters": {"comparison": "AI vs none", "keep": 1},
                },
                "refs": [],
            }
        ],
    }
    script = design_llm.propose_turn(_fake_client(reply), "x", [], PAPERS, TEMPLATES)
    assert script.moves[0].patch["parameters"] == {"keep": 1}


# ------------------------------------------------ decision follow-ups: no invented
# motives, short replies, no unrecorded facts.


def test_system_prompt_forbids_inventing_the_researchers_reasons():
    prompt = design_llm.SYSTEM_PROMPT
    assert "Never state, guess or imply why the researcher accepted" in prompt


def test_system_prompt_only_restates_recorded_details():
    assert (
        "only restate details that appear as accepted moves in the state block "
        "or as cards in this turn"
    ) in design_llm.SYSTEM_PROMPT


def test_decision_followup_prompt_is_neutral_and_short():
    from middleware import design_assistant

    for action in ("accepted", "rejected", "noted", "undone"):
        directive = design_assistant._directive(
            {
                "decisionAction": action,
                "intent": "answer",
                "batchIntake": False,
                "understanding": {},
                "profile": None,
            },
            None,
        )
        assert "Never state, guess or imply why the researcher" in directive
        assert "at most three sentences" in directive
        assert "explain what the proposal was trying to solve" not in directive


def test_decision_followup_reply_is_capped_to_a_short_length():
    long = " ".join(f"Distinct sentence number {i} is here." for i in range(40))
    client = _fake_client({"text": long, "moves": []})
    turn = design_llm.propose_turn(
        client, "t", [], PAPERS, TEMPLATES, decision_followup=True
    )
    assert turn.text == "Noted."
    normal = design_llm.propose_turn(client, "t", [], PAPERS, TEMPLATES)
    assert 100 < len(normal.text) <= 700


def test_decision_followup_cap_applies_when_streaming_falls_back():
    long = " ".join(f"Distinct sentence number {i} is here." for i in range(40))
    client = _fake_client({"text": long, "moves": []})  # no .stream
    gen = design_llm.propose_turn_streaming(
        client, "t", [], PAPERS, TEMPLATES, decision_followup=True
    )
    try:
        next(gen)
    except StopIteration as stop:
        turn = stop.value
    assert len(turn.text) <= 400


def test_strip_attributed_motives_removes_invented_reasons():
    text = (
        "You rejected the within-subjects design move because you wanted to "
        "clarify the setup first. Who will take part?"
    )
    assert design_llm.strip_attributed_motives(text) == "Who will take part?"
    text2 = "The rejected move was trying to name the population. What size?"
    assert design_llm.strip_attributed_motives(text2) == "What size?"
    assert design_llm.strip_attributed_motives("Noted. How many?") == "Noted. How many?"


def test_decision_followup_reply_drops_invented_motives():
    reply = {
        "text": "Noted: you rejected that choice. You did so because you wanted "
        "a larger sample. How many participants can you recruit?",
        "moves": [],
    }
    turn = design_llm.propose_turn(
        _fake_client(reply), "t", [], PAPERS, TEMPLATES, decision_followup=True
    )
    assert "because you" not in turn.text
    assert turn.text == "Noted."


def test_system_prompt_sets_expert_voice_rules():
    prompt = design_llm.SYSTEM_PROMPT
    assert "EXPERT VOICE" in prompt
    assert "Never define basic research concepts" in prompt
    assert "Never restate the brief" in prompt
    assert "no negative lists" in prompt
    assert "exactly one next question" in prompt
    assert "one imperative sentence" in prompt


def test_normal_reply_cap_is_700_chars_and_decision_cap_stays_400():
    assert design_llm.REPLY_TEXT_MAX_CHARS == 700
    assert design_llm.DECISION_REPLY_MAX_CHARS == 400
    long = " ".join(f"Distinct sentence number {i} is here." for i in range(60))
    assert len(design_llm.cap_reply_text(long)) <= 700


def test_strip_filler_removes_openers_and_student_assumptions():
    out = design_llm.strip_filler(
        "Great question. Certainly! I understand. As an AI, I think so. "
        "Use 12 participants. This is feasible for a course project."
    )
    assert out == "Use 12 participants."


def test_strip_filler_keeps_substantive_text():
    text = "Counterbalance order. Fixed order confounds learning with AI use."
    assert design_llm.strip_filler(text) == text


def test_strip_filler_preserves_reply_structure():
    text = (
        "Compare both designs.\n\nWithin-subjects risks learning.\n"
        "Between-subjects needs more participants."
    )
    assert design_llm.strip_filler(text) == text
    assert design_llm.strip_filler("Great question.\n\n" + text) == text


def test_clean_reply_strips_filler():
    out = design_llm._clean_reply("Certainly. Fix AI-first?", [], [])
    assert out == "Fix AI-first?"


def test_batch_and_requested_explanations_have_room_for_material_tradeoffs():
    text = " ".join(
        f"Decision {i} has a distinct material tradeoff to inspect." for i in range(50)
    )
    reply = design_llm._clean_reply(
        text, [], [], directive="QUESTION ABOUT WHAT YOU ALREADY SAID"
    )
    assert 700 < len(reply) <= design_llm.EXPLAIN_REPLY_MAX_CHARS == 900
    assert reply.endswith(".")
    assert len(design_llm._clean_reply(text, [], [])) <= 700
    batch = design_llm._clean_reply(
        text, [], [], directive="BATCH INTAKE", has_cards=True
    )
    assert len(batch) <= design_llm.CARDS_REPLY_MAX_CHARS == 520


def test_batch_budget_applies_to_blocking_and_streaming_provider_calls():
    text = " ".join(
        f"Decision {i} has a distinct material tradeoff." for i in range(35)
    )
    payload = json.dumps({"text": text, "moves": []})
    budgets = []

    class Client:
        base_url = "https://example.invalid"
        api_key = "synthetic"
        model = "configurable-model"

        def post(self, _url, body, _headers):
            budgets.append(body["max_tokens"])
            return {"choices": [{"message": {"content": payload}}]}

        def stream(self, _url, body, _headers):
            budgets.append(body["max_tokens"])
            yield payload

    blocking = design_llm.propose_turn(Client(), "brief", [], [], [], "BATCH INTAKE")
    stream = design_llm.propose_turn_streaming(
        Client(), "brief", [], [], [], "BATCH INTAKE"
    )
    while True:
        try:
            next(stream)
        except StopIteration as stop:
            streamed = stop.value
            break
    assert blocking.text == streamed.text
    assert len(blocking.text) <= 700
    assert budgets == [design_llm.MAX_TOKENS * 2] * 2


def test_tighten_proposal_trims_trailing_rationale():
    t = design_llm.tighten_proposal
    assert (
        t("Set 12 participants (within-subjects), because power is adequate.")
        == "Set 12 participants (within-subjects)."
    )
    assert t("Add task completion time. This captures speed.") == (
        "Add task completion time."
    )
    assert t("Use a paired design so that order effects cancel") == (
        "Use a paired design."
    )
    assert t("Set 12 participants.") == "Set 12 participants."


def test_parse_moves_tightens_proposal():
    moves = design_llm._parse_moves(
        [
            {
                "kind": "caution",
                "target": "x",
                "proposal": (
                    "Counterbalance order, since a fixed order confounds learning."
                ),
            }
        ],
        set(),
    )
    assert moves[0].proposal == "Counterbalance order."


def _stance(intent):
    return {
        "decisionAction": None,
        "intent": intent,
        "batchIntake": False,
        "understanding": {
            "missing": ["task"],
            "missingLabels": ["task"],
            "known": [],
            "facetsNeeded": 5,
        },
        "profile": None,
        "mayProposeDesign": False,
        "nextQuestion": "What will participants do?",
    }


def test_directives_use_expert_voice():
    from middleware import design_assistant

    stuck = design_assistant._directive(_stance("needs-scaffolding"), None)
    assert "plain language" not in stuck
    assert "Do not define" in stuck
    step = design_assistant._directive(_stance("answer"), None)
    assert "Reflect their idea" not in step
    assert "Never restate" in step
    assert "exactly one" in step


def test_canned_replies_are_short_and_name_the_fix():
    from middleware import design_assistant as da

    assert "MISTRAL_API_KEY" in da.NO_MODEL
    assert len(da.NO_MODEL) <= 160
    assert "apolog" not in da.MODEL_SILENT.lower()
    assert len(da.MODEL_SILENT) <= 170


# ------------------------------------------------ server-side enforcement of
# expert brevity (live-model fixtures; no model needed).

LIVE_USER = (
    "We want to know whether AI code completion changes how experienced developers "
    "review code. Thinking of a within-subjects design with about 16 developers."
)
SERBIA_TITLE = (
    "AI ASSISTANTS IN PROGRAMMING: MULTIDIMENSIONAL ANALYSIS OF USEFULNESS, "
    "TRUST AND PRODUCTIVITY"
)
LIVE_PAPERS = [
    {
        "ref": "corpus:serbia",
        "title": SERBIA_TITLE,
        "authors": ["Jovanovic, M.", "Petrovic, A."],
        "year": 2024,
    },
    {
        "ref": "corpus:metr",
        "title": "AI-Assisted Programming Decreases the Productivity of Experienced Developers",  # noqa: E501
        "authors": "Smith, J.",
        "year": 2025,
    },
]
LIVE_REPLY = (
    "The study is a within-subjects design with 16 experienced developers. "
    "The research question is whether AI code completion changes how developers "
    "review code. This is a classic human-AI synergy study: the key question is "
    "whether the AI changes the review process rather than only the output. "
    "The literature shows that AI can alter developer attitudes "
    "(AI-Assisted Programming Decreases the Productivity of Experienced Developers). "
    "The risk here is conflating output changes with process changes, such as more "
    "or fewer comments. The template Within-subject human-AI synergy comparison is "
    "the closest fit because it separates the two. The Randomized controlled trial "
    "of AI assistance on real tasks is too broad for this question. The Self-report-only "  # noqa: E501
    f"survey is insufficient alone because it misses behaviour ({SERBIA_TITLE})."
)


def test_cards_turn_prose_is_three_sentences_and_520_chars_and_starts_past_restatement():  # noqa: E501
    out = design_llm._clean_reply(
        LIVE_REPLY, LIVE_PAPERS, [], user_text=LIVE_USER, has_cards=True
    )
    assert len(out) <= 520
    assert out.startswith("This is a classic human-AI synergy study")
    assert "is too broad" not in out and "is insufficient" not in out
    assert "MULTIDIMENSIONAL" not in out
    sentences = design_llm._split_sentences(out)
    assert len(sentences) <= 3


def test_restating_leading_sentences_are_dropped_but_never_all():
    out = design_llm.drop_restatement(
        "Within-subjects design with 16 developers. Fix AI-first?", LIVE_USER
    )
    assert out == "Fix AI-first?"
    only = "Within-subjects design with 16 experienced developers."
    assert design_llm.drop_restatement(only, LIVE_USER) == only


def test_rejected_alternative_sentences_are_dropped():
    out = design_llm.drop_rejected_alternatives(
        "Use the crossover. The rejected trial is too broad. "
        "The unused alternative survey is insufficient alone. "
        "This template does not prescribe a test. Order effects matter."
    )
    assert out == (
        "Use the crossover. This template does not prescribe a test. "
        "Order effects matter."
    )


def test_inline_full_title_citations_become_surname_year():
    out = design_llm.shorten_citations(
        f"Trust differs (AI-Assisted Programming Decreases the Productivity of "
        f"Experienced Developers) and ({SERBIA_TITLE}).",
        LIVE_PAPERS,
    )
    assert "(Smith 2025)" in out
    assert "(Jovanovic et al. 2024)" in out


def test_citation_without_authors_uses_sentence_case_title_year():
    papers = [{"ref": "r", "title": SERBIA_TITLE, "year": 2024}]
    out = design_llm.shorten_citations(f"Seen ({SERBIA_TITLE}).", papers)
    inner = out[out.index("(") + 1 : out.index(")")]
    assert inner.endswith("2024") and inner != inner.upper()
    assert len(inner) <= 70 and inner.startswith("Ai assistants")


def test_citation_tolerates_typos_in_the_models_copy_of_the_title():
    typo = SERBIA_TITLE.replace("OF USEFULNESS", "OFUSEFULNESS")
    out = design_llm.shorten_citations(f"Seen ({typo}).", LIVE_PAPERS)
    assert "(Jovanovic et al. 2024)" in out


def test_missing_question_appends_next_question_only_without_cards():
    plain = design_llm._clean_reply(
        "Fixed order confounds learning with AI use.",
        [],
        [],
        has_cards=False,
        next_question="Counterbalance order, or fix AI-first?",
    )
    assert plain.endswith("Counterbalance order, or fix AI-first?")
    carded = design_llm._clean_reply(
        "Fixed order confounds learning with AI use.",
        [],
        [],
        has_cards=True,
        next_question="Counterbalance order, or fix AI-first?",
    )
    assert "?" not in carded
    fallback = design_llm._clean_reply(
        "Fixed order confounds.", [], [], has_cards=False
    )
    assert fallback == "Fixed order confounds."


def test_existing_question_is_kept_and_not_duplicated():
    out = design_llm._clean_reply(
        "Fixed order confounds learning. Counterbalance? Also this is extra. And more.",
        [],
        [],
        has_cards=True,
        next_question="Other?",
    )
    assert out.count("?") == 1 and out.endswith("Counterbalance?")


def test_extended_cap_only_for_explain_turns_and_is_900():
    long = " ".join(
        f"Distinct explanatory sentence number {i} is here." for i in range(60)
    )
    explain = design_llm._clean_reply(
        long, [], [], directive="THIS TURN IS A QUESTION ABOUT WHAT YOU ALREADY SAID."
    )
    assert 700 < len(explain) <= 900
    batch = design_llm._clean_reply(
        long, [], [], directive="BATCH INTAKE.", has_cards=True
    )
    assert len(batch) <= 520


def _mv(kind, proposal, section=None, value=None):
    move = {"kind": kind, "target": "t", "proposal": proposal}
    if section:
        move["patch"] = {"section": section, "op": "set", "value": value}
    return move


def test_parse_moves_collapses_duplicate_participant_cards():
    moves = design_llm._parse_moves(
        [
            _mv("set-parameter", "Plan for 16 participants.", "participants", "16"),
            _mv(
                "set-parameter",
                "Set 16 participants (within-subjects).",
                "participants",
                "16 participants (within-subjects)",
            ),
            _mv("set-parameter", "Set 20 participants.", "participants", "20"),
        ],
        set(),
    )
    assert [m.proposal for m in moves] == [
        "Plan for 16 participants.",
        "Set 20 participants.",
    ]


def test_parse_moves_drops_empty_cautions():
    for text in ("None.", "N/A", "No caution.", "No cautions", ""):
        assert design_llm._parse_moves([_mv("caution", text)], set()) == ()
    kept = design_llm._parse_moves(
        [_mv("caution", "Order effects threaten validity.")], set()
    )
    assert len(kept) == 1


def test_parse_moves_caps_cards_per_turn():
    raw = [
        _mv("add-measure", f"Add measure {i}.", "measures", f"measure number {i} alpha")
        for i in range(10)
    ]
    assert len(design_llm._parse_moves(raw, set())) == 5
    assert len(design_llm._parse_moves(raw, set(), max_cards=8)) == 8


def test_decision_followup_reply_is_deterministic():
    lecture = (
        "Noted: you rejected the within-subjects proposal. The field expects "
        "explicit control over order effects in human-AI studies."
    )
    out = design_llm._clean_reply(
        lecture, [], [], decision_followup=True, next_question="Who takes part?"
    )
    assert out == "Noted. Who takes part?"
    assert design_llm._clean_reply(lecture, [], [], decision_followup=True) == "Noted."


# ------------------------------------------------ real shapes from a live run
# (voice-study-2: persisted design_moves and conversation_turns rows).


def _pm(kind, target, proposal, patch):
    from middleware.design_assistant import ProposedMove

    return ProposedMove(kind, target, proposal, patch, ())


LIVE_MOVES = (
    _pm(
        "set-field",
        "participants.design",
        "Use a within-subjects design where each participant completes both conditions.",  # noqa: E501
        {
            "op": "set-field",
            "path": ["participants", "design"],
            "value": "within-subjects",
        },
    ),
    _pm(
        "set-field",
        "participants.planned",
        "Plan for 16 participants.",
        {"op": "set-field", "path": ["participants", "planned"], "value": 16},
    ),
    _pm(
        "set-parameter",
        "participants[]",
        "Recruit experienced developers as the study population.",
        {"section": "participants", "op": "append", "value": "experienced developers"},
    ),
    _pm(
        "set-field",
        "participants.planned",
        "Set 16 participants (within-subjects).",
        {"op": "set-field", "path": ["participants", "planned"], "value": 16},
    ),
    _pm(
        "set-field",
        "participants.description",
        "Set population to experienced developers.",
        {
            "op": "set-field",
            "path": ["participants", "description"],
            "value": "Experienced developers",
        },
    ),
    _pm(
        "add-rq",
        "researchQuestions[]",
        "Declare research question: Does AI code completion change how experienced developers review code?",  # noqa: E501
        {
            "section": "researchQuestions",
            "op": "append",
            "value": "Does AI code completion change how experienced developers review code?",  # noqa: E501
        },
    ),
    _pm(
        "choose-template",
        "templateId",
        "Choose the within-subjects crossover template.",
        {"templateId": "hai-eval-synergy-v1", "parameters": {}},
    ),
)


def test_dedupe_moves_is_semantic_across_kinds_and_paths():
    kept = design_llm.dedupe_moves(LIVE_MOVES, max_cards=5)
    assert [m.proposal for m in kept] == [
        LIVE_MOVES[0].proposal,
        "Plan for 16 participants.",
        "Recruit experienced developers as the study population.",
        LIVE_MOVES[5].proposal,
        LIVE_MOVES[6].proposal,
    ]
    assert len(design_llm.dedupe_moves(LIVE_MOVES * 1, max_cards=3)) == 3


def test_assemble_level_merge_of_explicit_and_model_moves_is_deduped():
    from middleware import design_assistant

    turn = design_assistant.Turn("t", LIVE_MOVES, None)
    out = design_assistant._dedupe_turn(turn, "a short partial idea")
    assert len(out.moves) == 5


LIVE_TURN3 = (
    "For a within-subjects study of AI code completion's effect on code review, "
    "the measures must capture both objective and subjective changes. The "
    "literature shows that AI-assisted review alters review time (Does AI Code "
    "Review Lead to Code Changes? A Case Study of GitHub Actions), comment quality "
    "(What Types of Code Review Comments Do Developers Most Frequently Resolve?), "
    "and perceived effort (AI ASSISTANTS IN PROGRAMMING: MULTIDIMENSIONAL ANALYSIS "
    "OFUSEFULNESS, CHANGES IN WORK ATTITUDES, AND FUTURE EXPECTATIONS FOR "
    "DEVELOPERS IN THE REPUBLIC OF SERBIA). Objective measures avoid the "
    "perception gap. The next question is: Do you want to measure review time, "
    "comment quality, or both, and how will you operationalize them?"
)


def test_uncandidate_title_parentheticals_are_shortened_too():
    out = design_llm.shorten_citations(LIVE_TURN3, [])
    assert "Case Study of GitHub Actions)" not in out
    assert "(Does AI Code Review Lead to Code" in out and "…" in out
    assert "MULTIDIMENSIONAL" not in out
    assert "(Ai assistants in programming" in out
    for m in __import__("re").finditer(r"\(([^()]+)\)", out):
        assert len(m.group(1)) <= 70


def test_next_question_scaffolding_prefix_is_removed():
    out = design_llm._clean_reply(LIVE_TURN3, [], [], has_cards=False)
    assert "The next question is" not in out
    assert out.endswith("operationalize them?")
    assert len(out) <= 700


def test_a_cited_paper_id_is_shown_as_a_short_citation_not_its_full_title():
    """The model cites papers by id. The id must become '(Surname Year)', not the
    full title: expanding ids to titles after shortening undid the shortening."""
    papers = [
        {
            "ref": "arxiv:2510.00001",
            "title": "AI-Assisted Programming Decreases the Productivity of Experienced "  # noqa: E501
            "Developers by Increasing the Technical Debt and Maintenance Burden",
            "authors": ["Maria Okafor", "Jan Lindqvist"],
            "year": 2025,
        }
    ]
    out = design_llm._clean_reply(
        "Experienced developers often overestimate their gains (arxiv:2510.00001). "
        "Which task do you want them to review?",
        papers,
        [],
        has_cards=True,
    )
    assert "Technical Debt and Maintenance Burden" not in out
    assert "Okafor" in out and "2025" in out
    assert out.rstrip().endswith("?")


def test_a_title_with_a_question_mark_does_not_break_the_reply_into_fragments():
    """Titles contain '?' and ':'. Citations must be shortened BEFORE the reply is
    split into sentences, or the title is cut in half (live: '(Does AI Code Review
    Lead to Code Changes?' with the parenthesis never closed)."""
    papers = [
        {
            "ref": "arxiv:2510.00002",
            "title": "Does AI Code Review Lead to Code Changes? A Case Study of GitHub Actions",  # noqa: E501
            "authors": ["Priya Raman"],
            "year": 2025,
        }
    ]
    out = design_llm._clean_reply(
        "AI review can change review patterns (arxiv:2510.00002). "
        "Objective measures avoid the perception gap. "
        "Which review task do you want to use?",
        papers,
        [],
        has_cards=True,
    )
    assert out.count("(") == out.count(")")
    assert "Raman" in out and "2025" in out
    assert "A Case Study of GitHub" not in out
    assert out.rstrip().endswith("Which review task do you want to use?")


def test_a_literal_title_with_a_question_mark_is_shortened_before_sentence_splitting():
    """Live shape: the model writes the title itself (not an id)."""
    papers = [
        {
            "ref": "arxiv:2510.00003",
            "title": "Does AI Code Review Lead to Code Changes? A Case Study of GitHub Actions",  # noqa: E501
            "authors": ["Priya Raman"],
            "year": 2025,
        }
    ]
    out = design_llm._clean_reply(
        "The literature shows that AI can change review patterns "
        "(Does AI Code Review Lead to Code Changes? A Case Study of GitHub Actions). "
        "Objective measures avoid the perception gap between felt and measured effects. "  # noqa: E501
        "Which review task do you want to use?",
        papers,
        [],
        has_cards=True,
    )
    assert out.count("(") == out.count(")"), out
    assert "A Case Study of GitHub" not in out, out
    assert "Raman" in out, out
    assert out.rstrip().endswith("Which review task do you want to use?"), out


def test_an_unmatched_long_title_never_leaves_sentence_punctuation_inside_the_cite():
    """Live (turn 1): the 3-sentence limiter split a shortened title at its '?' and
    kept '(Does AI Code Review Lead to Code Changes?' with no closing parenthesis."""
    text = (
        "The research question is about how AI code completion affects review behaviour. "  # noqa: E501
        "This is a classic human-AI synergy study with objective and subjective outcomes. "  # noqa: E501
        "The literature shows that AI can change review patterns "
        "(Does AI Code Review Lead to Code Changes? A Case Study of GitHub Actions). "
        "Objective measures avoid the perception gap between felt and measured effects."
    )
    out = design_llm._clean_reply(text, [], [], has_cards=True)
    assert out.count("(") == out.count(")"), out
    inside = __import__("re").findall(r"\(([^)]*)\)", out)
    assert all(not any(ch in cite for ch in "?!:") for cite in inside), out
    assert "Lead to Code Changes" in out or "Does AI Code Review" in out, out


def test_reply_shortening_preserves_sample_size_and_capture_limitations():
    text = (
        "The sample is not sufficient for this effect size. "
        "This capture will not include code correctness. Consider a pilot?"
    )
    assert design_llm._clean_reply(text, [], []) == text



def test_parse_moves_keeps_distinct_measures_with_the_same_number():
    moves = design_llm._parse_moves(
        [
            _mv(
                "add-measure",
                "Track 2026 completion time.",
                "measures",
                "2026 completion time",
            ),
            _mv(
                "add-measure", "Track 2026 correctness.", "measures", "2026 correctness"
            ),
        ],
        set(),
    )
    assert len(moves) == 2
