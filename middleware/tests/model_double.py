"""A test double for the language model the design conversation needs.

The conversation requires a model (``design_assistant.ModelUnavailable``), so
tests need one that is hermetic and deterministic. This is that: a provider
whose ``post`` never touches the network and returns replies the test chose.

It is emphatically *not* the keyword-scripted assistant that used to ship in
production. The difference is where it lives and what it is for: this stands
in for the model so the surrounding machinery - retrieval, grounding
resolution, the stance gate, the repetition filter, the compiler - can be
exercised for real. Everything under test is the real implementation; only
the model's own words are supplied.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable

from middleware import assistant

#: A reply the model might give: prose plus the moves it proposes.
Reply = dict


def _provider(handler: Callable[[dict], Reply], captured: list | None = None):
    def post(url, body, headers):
        if captured is not None:
            captured.append(body)
        return {
            "choices": [{"message": {"content": json.dumps(handler(body))}}]
        }

    return assistant.MistralProvider("test-key", post=post)


def always(reply: Reply, captured: list | None = None):
    """A model that gives the same reply to everything."""
    return _provider(lambda _body: reply, captured)


#: The design prompt's user message is ``"<researcher text>\n\nCandidate menu
#: this turn:\n..."`` (``design_llm._user_message``). The double keys on the
#: researcher's half only - the menu names templates like
#: ``survey-self-report-v1``, so matching the whole message would route on the
#: platform's own vocabulary rather than the researcher's.
_MENU_MARKER = "\n\nCandidate menu this turn:"


def _researcher_text(body: dict) -> str | None:
    """What the researcher actually said this turn, or None when the call is
    not a design turn (matching's query expansion shares this provider)."""
    message = body["messages"][-1]["content"]
    head, marker, _ = message.partition(_MENU_MARKER)
    return head if marker else None


def _directive(body: dict) -> str:
    """This turn's stance instruction - the system message the server puts
    after the history (``design_llm._messages``). A real model is expected to
    obey it, so the double does too."""
    systems = [m["content"] for m in body["messages"] if m["role"] == "system"]
    return systems[-1] if len(systems) > 1 else ""


def _menu_templates(body: dict) -> list[str]:
    """The template ids on this turn's candidate menu, best match first.

    Menu lines are ``"- <templateId>: <title> (<shape>)"`` for templates and
    ``"- <paperRef>: <title>"`` for papers (``design_llm._candidate_menu``);
    template ids end in a version suffix, which is what separates the two.
    """
    _, marker, menu = body["messages"][-1]["content"].partition(_MENU_MARKER)
    if not marker:
        return []
    ids = []
    for line in menu.splitlines():
        line = line.strip()
        if line.startswith("- ") and ":" in line:
            candidate = line[2:].split(":", 1)[0].strip()
            if "-v" in candidate and candidate.rsplit("-v", 1)[-1].isdigit():
                ids.append(candidate)
    return ids


def _pick_template(body: dict, prefer: str | None) -> str | None:
    """The template the double adopts: ``prefer`` when the menu offers it,
    otherwise the menu's own best match."""
    ids = _menu_templates(body)
    if prefer and prefer in ids:
        return prefer
    return ids[0] if ids else None


def in_turn(replies: Iterable[Reply], captured: list | None = None):
    """A model that gives each reply once, in order, then repeats the last.

    The design conversation makes one model call per turn, but *other*
    machinery (matching's query expansion) can call the same provider, so
    replies are consumed only by design-conversation calls - identified by
    the candidate menu the design prompt always carries.
    """
    queue = list(replies)
    assert queue, "in_turn needs at least one reply"
    state = {"i": 0}

    def handler(body: dict) -> Reply:
        if _researcher_text(body) is None:
            return {"text": "", "moves": []}
        reply = queue[min(state["i"], len(queue) - 1)]
        state["i"] += 1
        return reply

    return _provider(handler, captured)


def silent(captured: list | None = None):
    """A model that replies with prose and proposes nothing."""
    return always({"text": "Noted.", "moves": []}, captured)


def outage():
    """A configured provider that fails on every call."""

    class _Raises:
        model = "test"
        api_key = "k"
        base_url = "https://example.invalid/chat/completions"

        def post(self, *a, **k):
            raise TimeoutError("simulated provider outage")

    return _Raises()


# --------------------------------------------------------------- move shapes
# Reusable move payloads, so a test says what it is exercising rather than
# restating the wire format each time.


def move(kind: str, section: str, value: str, *, refs: tuple[str, ...] = ()) -> dict:
    return {
        "kind": kind,
        "target": f"{section}[]",
        "proposal": value,
        "patch": {"section": section, "op": "append", "value": value},
        "refs": list(refs),
    }


def field(path: tuple[str, ...], value: object) -> dict:
    return {
        "kind": "set-field",
        "target": ".".join(path),
        "proposal": f"Set {'.'.join(path)} to {value}.",
        "patch": {"op": "set-field", "path": list(path), "value": value},
        "refs": [],
    }


def template(template_id: str, *, refs: tuple[str, ...] = ()) -> dict:
    return {
        "kind": "choose-template",
        "target": "design",
        "proposal": f"Adopt the {template_id} template.",
        "patch": {"templateId": template_id, "parameters": {}},
        "refs": list(refs),
    }


def caution(text: str, *, refs: tuple[str, ...] = ()) -> dict:
    return {
        "kind": "caution",
        "target": "measures",
        "proposal": text,
        "patch": None,
        "refs": list(refs),
    }


def instrument(minutes: int = 45) -> dict:
    from middleware import compiler

    return {
        "kind": "add-instrument",
        "target": "instruments.tern",
        "proposal": "Add the standard TERN capture.",
        "patch": {
            "section": "instruments",
            "op": "add-instrument",
            "name": "tern",
            "config": compiler.default_capture_instrument(minutes),
        },
        "refs": [],
    }


def plausible(captured: list | None = None, prefer: str | None = "metr-rct-v1"):
    """A double that behaves like a competent, compliant model.

    It reads this turn's directive - the stance the server computes and puts
    in a system message - and does what it says: ask the named question when
    the study isn't understood yet, propose a design when invited to, answer
    rather than re-propose when the researcher asked a question. Only when
    the directive leaves it free does it respond to the researcher's words.

    ``prefer`` names the template it adopts when the menu offers it, so a
    test that needs a *known* protocol to enroll against gets one instead of
    whatever currently ranks top. Pass ``None`` to take the menu's own best
    match, which is what a real model would most likely do.

    Following the directive (rather than pattern-matching the researcher) is
    what makes this a stand-in for a model instead of a re-implementation of
    the keyword assistant that was removed. It also means the tests exercise
    the *enforcement* layer honestly: the double can be told to misbehave,
    and the server still has to stop it.
    """

    def handler(body: dict) -> Reply:
        said = _researcher_text(body)
        if said is None:
            return {"text": "", "moves": []}
        directive = _directive(body)
        said = said.lower()

        if "THIS TURN IS A QUESTION ABOUT WHAT YOU ALREADY SAID" in directive:
            return {
                "text": "I proposed that because the corpus supports it.",
                "moves": [],
            }

        moves: list[dict] = []
        # Instrument changes: asked for outright, so they are acted on rather
        # than discussed. These ride the same move path as everything else,
        # which is the point of the amendment tests that use them.
        if "agent-capture" in said or "agent capture" in said:
            return {
                "text": "That adds a new data stream, which is consent-relevant.",
                "moves": [agent_capture()],
            }
        if "threshold" in said or "stuck" in said:
            return {
                "text": "That's instrument tuning, not a consent change.",
                "moves": [stuck_threshold(120)],
            }
        if "self-report" in said or "survey" in said:
            moves.append(
                caution(
                    "Self-reported speed diverges from measured speed; pair it "
                    "with an objective task-time measure.",
                    refs=("corpus:metr-early-2025-dev-productivity",),
                )
            )
        if "trust" in said or "junior" in said:
            moves.extend(
                [
                    move(
                        "add-rq",
                        "researchQuestions",
                        "Do juniors accept AI code with less review than seniors?",
                        refs=("corpus:trust-in-ai-code-generation",),
                    ),
                    move(
                        "add-measure",
                        "measures",
                        "Review latency before accept/reject",
                        refs=("corpus:insecure-code-with-ai-assistants",),
                    ),
                ]
            )

        # A design shape is offered when the researcher asks for one or names
        # one themselves - not the moment the server stops forbidding it. A
        # model that proposes a template the instant it is allowed to is
        # exactly the over-eager behaviour the stance gate exists to temper,
        # so the double waits to be asked, as a good one would.
        invited = (
            "explicitly asked you to name a design" in directive
            or "named a design themselves" in directive
        )
        if not invited:
            return {
                "text": "Tell me more — who takes part, and what will they do?",
                "moves": moves,
            }

        template_id = _pick_template(body, prefer)
        if template_id:
            moves.append(
                template(
                    template_id,
                    refs=("corpus:metr-early-2025-dev-productivity",),
                )
            )
        return {
            "text": "Here's the shape I'd use, and why.",
            "moves": moves,
        }

    return _provider(handler, captured)


def agent_capture(policy: str = "metadata-only") -> dict:
    """Add the agent-capture instrument — a new data stream, so the amendment
    path treats it as consent-relevant."""
    return {
        "kind": "add-instrument",
        "target": "instruments.agentCapture",
        "proposal": "Add the agent-capture instrument (Claude Code adapter).",
        "patch": {
            "section": "instruments",
            "op": "add-instrument",
            "name": "agentCapture",
            "config": {"adapter": "claude-code", "contentPolicy": policy},
        },
        "refs": [],
    }


def stuck_threshold(seconds: int) -> dict:
    """Retune the stuck detector — a config tweak, not a new data stream."""
    return {
        "kind": "reconfigure-instrument",
        "target": "instruments.tern.stuck.thresholdSeconds",
        "proposal": f"Raise the stuck-detector threshold to {seconds}s.",
        "patch": {
            "section": "instruments",
            "op": "reconfigure",
            "name": "tern",
            "path": ["stuck", "thresholdSeconds"],
            "value": seconds,
        },
        "refs": [],
    }


def prescription(recipe_id: str, rq: str = "RQ-1") -> dict:
    return {
        "kind": "prescribe-statistics",
        "target": "analysisPlan",
        "proposal": f"Analyse with {recipe_id}.",
        "patch": {"recipeId": recipe_id, "rq": rq},
        "refs": [],
    }
