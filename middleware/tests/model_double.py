"""A test double for the language model the design conversation needs."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable

from middleware import assistant

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


_MENU_MARKER = "\n\nCandidate menu this turn:"


def _researcher_text(body: dict) -> str | None:
    """
    What the researcher actually said this turn, or None when the call is not a design
    turn (matching's query expansion shares this provider).
    """
    message = body["messages"][-1]["content"]
    head, marker, _ = message.partition(_MENU_MARKER)
    return head if marker else None


def _directive(body: dict) -> str:
    """
    This turn's stance instruction - the system message the server puts after the
    history (``design_llm._messages``).
    """
    systems = [m["content"] for m in body["messages"] if m["role"] == "system"]
    return systems[-1] if len(systems) > 1 else ""


def _menu_templates(body: dict) -> list[str]:
    """The template ids on this turn's candidate menu, best match first."""
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
    """
    The template the double adopts: ``prefer`` when the menu offers it, otherwise the
    menu's own best match.
    """
    ids = _menu_templates(body)
    if prefer and prefer in ids:
        return prefer
    return ids[0] if ids else None


def in_turn(replies: Iterable[Reply], captured: list | None = None):
    """A model that gives each reply once, in order, then repeats the last."""
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


def merge(
    template_ids: tuple[str, ...], reason: str, *, refs: tuple[str, ...] = ()
) -> dict:
    return {
        "kind": "merge-templates",
        "target": "design",
        "proposal": f"Merge {', '.join(template_ids)}.",
        "patch": {"templateIds": list(template_ids), "reason": reason},
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
    """A double that behaves like a competent, compliant model."""

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

        invited = (
            "explicitly asked you to name a design" in directive
            or "named a design themselves" in directive
        )
        if not invited:
            return {
                "text": "Tell me more  -  who takes part, and what will they do?",
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
    """
    Add the agent-capture instrument  -  a new data stream, so the amendment path treats
    it as consent-relevant.
    """
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
    """Retune the stuck detector  -  a config tweak, not a new data stream."""
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
