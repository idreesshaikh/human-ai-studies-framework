"""Unit tests for the LLM-driven design-conversation seam (FR-CONV-1.4).

Pure tests against ``design_llm.propose_turn`` with a fake, injectable
provider (mirrors how ``test_knowledge_layer.py`` drives
``assistant.MistralProvider`` with a scripted ``post``) — no network, no
HTTP layer. The end-to-end wiring through ``/conversation/turns`` is
covered separately in ``test_conversation.py``.
"""

import json

from middleware import assistant, design_llm

PAPERS = [
    {"ref": "corpus:trust-in-ai-code-generation", "title": "Trust in AI Code"},
    {"ref": "corpus:metr-early-2025-dev-productivity", "title": "METR Productivity"},
]
TEMPLATES = [
    {"templateId": "metr-rct-v1", "title": "METR RCT", "designShape": "paired"},
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
    """Wall #3: a citation the model invents (not in the menu this turn)
    never survives, even though the JSON is otherwise well-formed."""
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
    """Regression: a non-caution move whose patch fails validation used to
    render anyway with `patch=None` - accepting it looked like it worked but
    silently never touched the draft (the "accepted but only noted" trap
    previously guarded only for choose-template). It must be dropped
    entirely instead of offered as a dud."""
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
    """Regression: an observed real-world failure. The model sometimes picks
    `add-instrument` for an ethics/consent move (it reads as "adding a
    policy") instead of `set-parameter`. `add-instrument`'s patch shape
    requires `section: "instruments"`, so the ethics patch used to be
    dropped outright - the move rendered as an accept/reject card but
    accepting it never touched the draft (ethics stayed empty forever, no
    matter how the researcher asked). The patch names a real section by
    shape, so it must be salvaged and compiled, whatever kind carried it."""
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
    """Section values must end up as strings: a list survives (the compiler
    flattens it into one entry per item), a number is stringified, and a
    dict value drops - and therefore drops the whole move, rather than
    poisoning the draft's schema or offering a move that no-ops."""
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
    """A choose-template move naming a template the registry doesn't have is
    dropped entirely — accepted, it would poison every future compile, and
    patch-less it would be the "accepted but only noted" trap."""
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
    """A conversational reply with nothing (yet) to propose is not a
    failure — it's an honest turn."""
    reply = {"text": "Tell me more about your population first.", "moves": []}
    client = _fake_client(reply)
    script = design_llm.propose_turn(client, "text", [], PAPERS, TEMPLATES)
    assert script is not None
    assert script.moves == ()


# ------------------------------------------------ design state (repetition +
# coverage steering): the structured block the prose history can't carry.


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
    assert "Measure review latency." in user  # accepted — do not re-propose
    assert "Run a three-arm condition split." in user  # rejected — do not re-pitch
    assert "Empty: participants, statisticalPlan" in user
    system = captured[0]["messages"][0]["content"]
    assert "NEVER re-propose" in system  # the anti-repetition rule is standing


def test_propose_turn_notes_the_accepted_templates_prescribed_statistics():
    captured: list = []
    client = _capturing_client({"text": "Noted.", "moves": []}, captured)
    state = {**DESIGN_STATE, "templateId": "metr-rct-v1", "empty": []}
    design_llm.propose_turn(
        client, "what next?", [], PAPERS, TEMPLATES, design_state=state
    )
    user = captured[0]["messages"][-1]["content"]
    assert "Template metr-rct-v1 is accepted and prescribes" in user
    assert "record or refine that prescription" in user
    # A template never closes the statisticalPlan section outright — the
    # regression that made the assistant refuse statisticalPlan moves.
    assert "do not propose a standalone statisticalPlan move" not in user


def test_cautions_render_as_advisory_and_the_prompt_says_they_fill_nothing():
    """A caution carries no patch: it must not read as draft content in the
    state block, and the standing prompt must say how ethics actually gets
    filled (the bug: two accepted ethics cautions, ethics slot still dark)."""
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
    assert "caution [ethics] (advisory — fills no section):" in user
    assert 'set-parameter` move' in design_llm.SYSTEM_PROMPT
    assert 'patch.section` "ethics"' in design_llm.SYSTEM_PROMPT


def test_propose_turn_without_design_state_omits_the_block():
    """Backward compatible: no state (stateless demo, first turn) — the
    request looks exactly like before."""
    captured: list = []
    client = _capturing_client({"text": "Noted.", "moves": []}, captured)
    design_llm.propose_turn(client, "what next?", [], PAPERS, TEMPLATES)
    assert all(
        "Design state so far" not in m["content"] for m in captured[0]["messages"]
    )
