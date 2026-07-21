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


def test_propose_turn_nulls_a_malformed_patch_but_keeps_the_move():
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
    assert len(script.moves) == 1
    assert script.moves[0].patch is None


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
