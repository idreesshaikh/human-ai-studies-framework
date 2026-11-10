"""One study plan behind the chat and the checklist.

A study in StudyLoop is described by a small plan: title, research questions,
design, two conditions, who takes part, how many, the task, the session length
and the outcome measures. The checklist form edits that plan directly. The chat
edits the same plan: one model call reads the conversation and returns the plan
as it should now be, and this module turns the difference into reviewable cards.

Both routes go through :func:`plan_moves`, so a study started in one can be
continued in the other at any point. The model decides what the study is. It
never writes protocol YAML: the compiler builds and validates the draft, and
nothing reaches the protocol until the researcher accepts the cards and applies
the reviewed draft. Whatever the model chose on its own is named as an
assumption in the reply.
"""

from __future__ import annotations

import json
import logging
import urllib.error

from protocol.measure_catalog import catalog_entry, measure_catalog
from pydantic import ValidationError

from middleware import assistant, compiler, elicitation
from middleware.schemas import QuickProtocolIn

log = logging.getLogger(__name__)

_COVARIATE_ONLY = {"S10"}
_MAX_TOKENS = 1100
_HISTORY_TURNS = 6
_HISTORY_CHARS = 600
_REPLY_CHARS = 700

_FIELD_LABELS = {
    "title": "the study title",
    "researchQuestions": "the research questions",
    "design": "the design",
    "conditions": "the two conditions",
    "participantDescription": "who takes part",
    "plannedParticipants": "the number of participants",
    "taskDescription": "the task",
    "sessionMinutes": "the session length",
    "measureIds": "the outcome measures",
}
PLAN_FIELDS = tuple(_FIELD_LABELS)

NOT_A_PLAN = (
    "I could not turn that into a study plan yet. Tell me the coding task, the "
    "two ways of working you want to compare, who takes part and what you want "
    "to measure, or fill in the checklist."
)


class Unreachable(RuntimeError):
    """The provider gave no answer. ``reason`` is "rejected" (bad key), "limited"
    (rate limit) or "down"."""

    def __init__(self, reason: str):
        super().__init__(f"model unreachable: {reason}")
        self.reason = reason


class PlanError(ValueError):
    """The plan cannot become a protocol; the message says why, for the researcher."""


def _catalog_lines() -> str:
    lines = []
    for entry in measure_catalog():
        if entry["id"] in _COVARIATE_ONLY:
            continue
        designs = [d for d, recipe in entry["recipeByDesign"].items() if recipe]
        lines.append(
            f"- {entry['id']}: {entry['construct']}. {entry['description']} "
            f"(analysable in: {', '.join(designs)})"
        )
    return "\n".join(lines)


def system_prompt() -> str:
    return (
        "You help a software-engineering researcher design a study in StudyLoop, "
        "a platform that runs controlled experiments comparing two ways of "
        "working on coding tasks in VS Code, typically with and without an AI "
        "assistant.\n\n"
        "You are given the current study plan and the researcher's latest "
        "message. Return the plan as it should be after this message. Keep the "
        "researcher's own words and numbers. Keep every field they did not ask "
        "to change exactly as it is. Where something is still undecided, choose "
        "what an experienced empirical software-engineering methodologist would "
        "choose for this particular study and list that field's name in "
        "`assumed`, so the researcher can see which choices were yours. When the "
        "message is a question or a comment, answer it in `reply` and return the "
        "plan unchanged. When the researcher asks for something a plan cannot "
        "hold, such as a third condition, keep the plan as it is and say so "
        "plainly in `reply`, with the closest design that would work. Describe "
        "in `reply` only what the plan you return actually contains.\n\n"
        "Outcome measures come from this catalog, because these are what the "
        "platform can capture and analyse:\n"
        f"{_catalog_lines()}\n"
        "Choose the measures that answer the research questions. A study about "
        "both performance and experience is best served by an observed outcome "
        "together with a self-report. Measure ids already in the current plan "
        "stay valid even when they are not in the catalog.\n\n"
        "Reply with one JSON object:\n"
        "{\n"
        '  "reply": two or three plain sentences to the researcher: what you '
        "changed and why, or the answer to their question,\n"
        '  "plan": {\n'
        '    "title": short study title,\n'
        '    "researchQuestions": one to three questions, each a full sentence,\n'
        '    "design": "within-subjects" or "between-subjects",\n'
        '    "conditions": two short plain-language names such as "without AI" '
        'and "with Copilot", the comparison baseline first,\n'
        '    "participantDescription": who takes part,\n'
        '    "plannedParticipants": a whole number,\n'
        '    "taskDescription": what participants do in a session,\n'
        '    "sessionMinutes": minutes per session,\n'
        '    "measureIds": measure ids\n'
        "  },\n"
        '  "assumed": names of plan fields you chose yourself in this turn,\n'
        '  "caution": the most important threat to validity for this design in '
        "one sentence, or an empty string\n"
        "}"
    )


def _clip(value: object, limit: int) -> str:
    # Only text is text: a nested object or a number is not a description.
    if not isinstance(value, str):
        return ""
    # Provider JSON may contain escaped, unpaired UTF-16 surrogates. Keep its
    # usable prose without passing an unencodable string to storage or the UI.
    value = value.encode("utf-8", errors="replace").decode("utf-8")
    return " ".join(value.split())[:limit].strip()


def plan_of(draft: dict | None) -> dict:
    """The study plan a protocol draft currently states; empty fields when unset."""
    draft = draft or {}
    participants = draft.get("participants") or {}
    session = draft.get("session") or {}
    return {
        "title": (draft.get("study") or {}).get("title") or "",
        "researchQuestions": [
            rq.get("text")
            for rq in draft.get("researchQuestions") or []
            if isinstance(rq, dict) and rq.get("text")
        ],
        "design": participants.get("design") or "",
        "conditions": [str(c) for c in draft.get("conditions") or []],
        "participantDescription": participants.get("description") or "",
        "plannedParticipants": participants.get("planned") or 0,
        "taskDescription": session.get("taskDescription") or "",
        "sessionMinutes": session.get("durationMinutes") or 0,
        "measureIds": [
            m["id"]
            for m in draft.get("measures") or []
            if isinstance(m, dict) and m.get("id")
        ],
    }


def _measure_names(draft: dict | None) -> dict[str, str]:
    return {
        m["id"]: str(m.get("construct") or m["id"])
        for m in (draft or {}).get("measures") or []
        if isinstance(m, dict) and m.get("id")
    }


_PLAN_LIMITS = {
    "title": "the study needs a title",
    "researchQuestions": "the study needs one to six research questions",
    "design": "the design is either within-subjects or between-subjects",
    "conditions": "a study here compares exactly two conditions",
    "participantDescription": "the plan has to say who takes part",
    "plannedParticipants": "the number of participants is between 4 and 1000",
    "taskDescription": "the plan has to describe the task",
    "sessionMinutes": "a session lasts between 15 and 180 minutes",
    "measures": "the plan needs at least one outcome measure from the catalog "
    "that this design can analyse",
}


def _body(plan: dict, current: dict | None) -> tuple[QuickProtocolIn | None, str]:
    """The model's plan as the checklist model, or (None, why it is unusable)."""
    design = plan.get("design")
    if design not in ("within-subjects", "between-subjects"):
        return None, _PLAN_LIMITS["design"]
    # Model output is untrusted JSON. Do not iterate strings as lists, use an
    # object as a catalog key, or truncate a fractional count into a new fact.
    for field, problem in (
        ("researchQuestions", "researchQuestions"),
        ("conditions", "conditions"),
        ("measureIds", "measures"),
    ):
        values = plan.get(field)
        if not isinstance(values, list) or not all(
            isinstance(value, str) for value in values
        ):
            return None, _PLAN_LIMITS[problem]
    custom = {
        ident: name
        for ident, name in _measure_names(current).items()
        if catalog_entry(ident) is None
    }
    fresh: list[str] = []
    kept: list[str] = []
    for ident in plan.get("measureIds") or []:
        ident = str(ident)
        entry = catalog_entry(ident)
        if ident in custom and ident not in kept:
            kept.append(ident)
        elif (
            entry
            and entry["id"] not in _COVARIATE_ONLY
            and entry["recipeByDesign"].get(design)
            and entry["id"] not in fresh
        ):
            fresh.append(entry["id"])
    fresh = fresh[: max(0, 6 - len(kept))]
    try:
        body = QuickProtocolIn(
            title=_clip(plan.get("title"), 160),
            researchQuestions=list(
                dict.fromkeys(
                    _clip(q, 500) for q in (plan.get("researchQuestions") or [])[:6]
                )
            ),
            design=design,
            # The quick path counterbalances every within-subjects comparison.
            counterbalanced=design == "within-subjects",
            conditions=[_clip(c, 80) for c in (plan.get("conditions") or [])],
            participantDescription=_clip(plan.get("participantDescription"), 240),
            plannedParticipants=plan.get("plannedParticipants"),
            taskDescription=_clip(plan.get("taskDescription"), 500),
            sessionMinutes=plan.get("sessionMinutes"),
            measures=[
                *[custom[i] for i in kept],
                *[catalog_entry(i)["construct"] for i in fresh],
            ],
            measureIds=fresh,
            existingMeasureIds=kept,
            typedMeasures=True,
        )
    except ValidationError as exc:
        log.info("the model's study plan is unusable: %s", exc)
        fields = dict.fromkeys(str(e["loc"][0]) for e in exc.errors() if e["loc"])
        reasons = [_PLAN_LIMITS[f] for f in fields if f in _PLAN_LIMITS]
        return None, _join(reasons[:3]) or "the plan is incomplete"
    except (TypeError, ValueError) as exc:
        log.info("the model's study plan is unusable: %s", exc)
        return None, "the plan is incomplete"
    return body, ""


def _task_title(task: str, limit: int = 80) -> str:
    """The task's first sentence, cut at a word boundary rather than mid-word."""
    first = task.split(". ")[0].rstrip(".")
    if len(first) <= limit:
        return first
    return first[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _moves(
    study_id: str,
    body: QuickProtocolIn,
    *,
    questions: list[str],
    conditions: list[str],
    measures: list[str],
    typed_mode: bool = True,
    preserved: dict[str, dict] | None = None,
    current: dict | None = None,
) -> list[dict]:
    """The design moves that realise an already validated study plan."""
    preserved = preserved or {}
    current = current or {}
    task = body.taskDescription.strip()
    population = body.participantDescription.strip()
    within = body.design == "within-subjects"
    return [
        {
            "kind": "choose-template",
            "target": "design",
            "proposal": (
                "Use a counterbalanced within-subjects comparison."
                if within
                else "Use a two-group between-subjects comparison."
            ),
            "patch": {
                "templateId": (
                    "within-subjects-crossover-v1" if within else "two-group-rct-v1"
                ),
                "parameters": {
                    "studyId": study_id,
                    "title": body.title.strip(),
                    "researchQuestion": questions[0],
                    "conditions": conditions,
                    "participantPlan": body.plannedParticipants,
                    "sessionMinutes": body.sessionMinutes,
                    "taskDescription": task,
                },
                "manual": True,
                "researchQuestions": questions,
                "typedMeasures": typed_mode,
                "baseProtocol": current
                if current.get("protocolVersion") == 6
                else None,
                "design": body.design,
                "counterbalanced": body.counterbalanced,
            },
        },
        *(
            {
                "kind": "add-rq",
                "target": "researchQuestions[]",
                "proposal": question,
                "patch": {
                    "section": "researchQuestions",
                    "op": "append",
                    "value": question,
                },
            }
            for question in questions[1:]
        ),
        {
            "kind": "set-field",
            "target": "participants.description",
            "proposal": f"Recruit {population}.",
            "patch": {
                "op": "set-field",
                "path": ["participants", "description"],
                "value": population,
            },
        },
        {
            "kind": "add-measure",
            "target": "measures[]",
            "proposal": "Measure " + ", ".join(measures) + ".",
            "patch": {
                "section": "measures",
                "op": "set" if typed_mode else "append",
                "value": [
                    *[preserved[ident] for ident in body.existingMeasureIds],
                    *[{"catalogId": ident} for ident in body.measureIds],
                ]
                if typed_mode
                else measures,
            },
        },
        {
            "kind": "declare-task",
            "target": "tasks[]",
            "proposal": task.rstrip(".") + ".",
            "patch": {
                "id": "primary-task",
                "title": _task_title(task),
                "description": task,
                "minutes": body.sessionMinutes,
                "conditions": conditions,
            },
        },
    ]


def plan_moves(
    study_id: str, body: QuickProtocolIn, current: dict | None
) -> list[dict]:
    """Validate a study plan against the current draft and return its design moves.

    The single entry point for the checklist and the chat. Raises
    :class:`PlanError` with a researcher-readable reason.
    """
    current = current or {}
    if any(
        not value.strip()
        for value in (body.title, body.participantDescription, body.taskDescription)
    ):
        raise PlanError("the study brief fields cannot be blank")
    questions = [question.strip() for question in body.researchQuestions]
    if any(not 10 <= len(question) <= 500 for question in questions):
        raise PlanError("each research question needs 10 to 500 characters")
    if len({question.casefold() for question in questions}) != len(questions):
        raise PlanError("research questions must be different")
    conditions = [condition.strip() for condition in body.conditions]
    if any(not condition or len(condition) > 80 for condition in conditions):
        raise PlanError(
            "each condition needs a short, non-empty name (80 characters max)"
        )
    if len({condition.casefold() for condition in conditions}) != 2:
        raise PlanError("the two conditions must be different")
    if body.design == "within-subjects" and not body.counterbalanced:
        raise PlanError(
            "within-subjects studies in this quick path must counterbalance "
            "condition order"
        )
    if body.design == "between-subjects" and body.plannedParticipants < 6:
        raise PlanError("between-subjects studies need at least 6 planned participants")
    scope = elicitation.classify_scope(
        [*questions, body.taskDescription, body.participantDescription]
    )
    if scope != "supported":
        raise PlanError(
            "Quick protocol is limited to task-based human–AI software-development "
            "studies that run in VS Code. Use the chat for a supported idea that "
            "needs shaping, or choose a different tool for exams, classroom, "
            "clinical, marketing, or general survey studies."
        )
    measures = [measure.strip() for measure in body.measures]
    if any(not measure or len(measure) > 100 for measure in measures):
        raise PlanError(
            "each outcome needs a short, non-empty description (100 characters max)"
        )
    if len({measure.casefold() for measure in measures}) != len(measures):
        raise PlanError("selected outcomes must be different")

    typed_mode = (
        body.typedMeasures
        or bool(body.measureIds)
        or bool(body.existingMeasureIds)
        or current.get("protocolVersion") == 6
    )
    preserved = {
        row["id"]: row for row in current.get("measures", []) if isinstance(row, dict)
    }
    if typed_mode:
        if len(body.measureIds) + len(body.existingMeasureIds) != len(measures) or len(
            set(body.measureIds)
        ) != len(body.measureIds):
            raise PlanError(
                "Choose a supported mapping for every outcome before saving."
            )
        if len(set(body.existingMeasureIds)) != len(body.existingMeasureIds) or any(
            ident not in preserved for ident in body.existingMeasureIds
        ):
            raise PlanError(
                "An existing measurement changed; reload the draft before editing."
            )
        for ident in body.measureIds:
            entry = catalog_entry(ident)
            if entry is None or (
                entry["id"] != "S10" and not entry["recipeByDesign"].get(body.design)
            ):
                raise PlanError(
                    "A selected outcome has no supported analysis for this design."
                )
        for ident in body.existingMeasureIds:
            recipe = preserved[ident]["analysisRecipe"]
            if (
                recipe == "paired-nonparametric" and body.design != "within-subjects"
            ) or (
                recipe in {"two-group-nonparametric", "two-proportion"}
                and body.design != "between-subjects"
            ):
                raise PlanError(
                    "The existing measurement analysis is incompatible "
                    "with this design; choose its analysis in Setup."
                )

    moves = _moves(
        study_id,
        body,
        questions=questions,
        conditions=conditions,
        measures=measures,
        typed_mode=typed_mode,
        preserved=preserved,
        current=current,
    )
    kept_recipes = {
        rq.get("text"): entry.get("recipes", [])
        for rq in current.get("researchQuestions") or []
        for entry in current.get("analysisPlan") or []
        if entry.get("rq") == rq.get("id")
    }
    preview = compiler.compile_moves([{**m, "status": "accepted"} for m in moves]).draft
    moves += [
        {
            "kind": "prescribe-statistics",
            "target": "analysisPlan",
            "proposal": f"Keep the {preserved[ident]['analysisRecipe']} analysis.",
            "patch": {"recipeId": preserved[ident]["analysisRecipe"], "rq": "RQ-1"},
        }
        for ident in body.existingMeasureIds
    ]
    moves += [
        {
            "kind": "prescribe-statistics",
            "target": "analysisPlan",
            "proposal": f"Keep the {recipe} analysis for {rq['id']}.",
            "patch": {"recipeId": recipe, "rq": rq["id"]},
        }
        for rq in preview.get("researchQuestions") or []
        for recipe in kept_recipes.get(rq.get("text"), [])
    ]
    return moves


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _opening_reply(
    body: QuickProtocolIn, assumed: list[str], caution: str, reply: str = ""
) -> str:
    design = (
        "a counterbalanced within-subjects comparison"
        if body.design == "within-subjects"
        else "a two-group between-subjects comparison"
    )
    # The model's own reading leads; the fixed sentence is only a fallback.
    parts = [
        reply
        or f"I read your brief as {design} of {body.conditions[0]} and "
        f"{body.conditions[1]} with {body.plannedParticipants} participants, "
        f"measuring {_join(body.measures)}."
    ]
    mine = [_FIELD_LABELS[name] for name in assumed if name in _FIELD_LABELS]
    if mine:
        parts.append(
            f"Your brief left these open, so they are my suggestions: {_join(mine)}."
        )
    if "plannedParticipants" in assumed:
        parts.append("The Plan tab calculates the sample size once the draft exists.")
    if caution:
        parts.append(caution)
    parts.append(
        "Accept the cards to build the draft, or tell me what to change first."
    )
    return " ".join(parts)


def _changed(before: dict, after: dict) -> list[str]:
    def norm(value: object) -> object:
        if isinstance(value, list):
            return [" ".join(str(v).split()) for v in value]
        return " ".join(str(value).split()) if isinstance(value, str) else value

    changed = [f for f in PLAN_FIELDS if norm(before.get(f)) != norm(after.get(f))]
    # Measures are a set: reordering them is not a change.
    if "measureIds" in changed and sorted(before["measureIds"]) == sorted(
        after["measureIds"]
    ):
        changed.remove("measureIds")
    return changed


def _ask(client, text: str, current_plan: dict, history: list[dict]) -> dict | None:
    messages = [{"role": "system", "content": system_prompt()}]
    for turn in history[-_HISTORY_TURNS:]:
        messages.append(
            {
                "role": "assistant" if turn.get("role") == "assistant" else "user",
                "content": _clip(turn.get("content"), _HISTORY_CHARS),
            }
        )
    messages.append(
        {
            "role": "user",
            "content": "Current plan:\n"
            + json.dumps(current_plan, ensure_ascii=False)
            + "\n\nResearcher's message:\n"
            + text,
        }
    )
    body = {
        "model": client.model,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "max_tokens": _MAX_TOKENS,
    }
    try:
        # One call: the transport already retries rate limits and outages with
        # backoff, and a second retry loop here would multiply the load.
        res = client.post(client.base_url, body, assistant.client_headers(client))
    except Exception as exc:
        log.info("study plan turn failed: %s", exc)
        code = exc.code if isinstance(exc, urllib.error.HTTPError) else None
        reason = (
            "rejected" if code in (401, 403) else "limited" if code == 429 else "down"
        )
        raise Unreachable(reason) from exc
    try:
        choices = res.get("choices") if isinstance(res, dict) else None
        if (
            not isinstance(choices, list)
            or not choices
            or not isinstance(choices[0], dict)
        ):
            return None
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            return None
        raw = json.loads(content)
    except (AttributeError, IndexError, TypeError, ValueError):
        return None
    return raw if isinstance(raw, dict) and isinstance(raw.get("plan"), dict) else None


def propose(
    client,
    text: str,
    study_id: str,
    current: dict | None = None,
    history: list[dict] | None = None,
) -> dict | None:
    """One chat turn against the study plan: ``{"text", "moves"}``, or None.

    None means the model answered with nothing plan-shaped and the caller should
    handle the turn another way. An answer with no change has no moves. Raises
    :class:`Unreachable` when the provider cannot be reached at all.
    """
    before = plan_of(current)
    raw = _ask(client, text, before, history or [])
    if raw is None:
        return None
    reply = _clip(raw.get("reply"), _REPLY_CHARS)
    body, problem = _body(raw["plan"], current)
    if body is None:
        # The model's prose describes a plan that was not applied, so it is not
        # shown: only the reason is.
        if not any(before.values()):
            return {"text": NOT_A_PLAN, "moves": []}
        return {
            "text": f"I could not apply that: {problem}. The plan is unchanged.",
            "moves": [],
        }
    after = {
        **{f: getattr(body, f) for f in PLAN_FIELDS if f != "measureIds"},
        "measureIds": [*body.existingMeasureIds, *body.measureIds],
    }
    changed = _changed(before, after)
    if not changed:
        return {
            "text": reply or "The plan is unchanged.",
            "moves": [],
        }
    try:
        moves = plan_moves(study_id, body, current)
    except PlanError as err:
        return {
            "text": f"I could not apply that: {err}. The plan is unchanged.",
            "moves": [],
        }
    # The compiler is the gate: a plan that does not build a valid protocol is
    # explained, never offered.
    built = compiler.compile_moves([{**m, "status": "accepted"} for m in moves])
    if not built.valid:
        log.info("study plan did not compile: %s %s", built.errors, built.unresolved)
        problems = _join([str(p) for p in [*built.errors, *built.unresolved][:3]])
        return {
            "text": f"That plan does not build a valid protocol: {problems}. "
            "The plan is unchanged.",
            "moves": [],
        }
    moves[0]["proposal"] += f" Research question: {body.researchQuestions[0]}"
    raw_assumed = raw.get("assumed")
    assumed = (
        [n for n in raw_assumed if isinstance(n, str)]
        if isinstance(raw_assumed, list)
        else []
    )
    caution = _clip(raw.get("caution"), 300)
    if not any(before.values()):
        return {"text": _opening_reply(body, assumed, caution, reply), "moves": moves}
    summary = "Changed: " + _join([_FIELD_LABELS[f] for f in changed]) + "."
    mine = [_FIELD_LABELS[n] for n in assumed if n in changed and n in _FIELD_LABELS]
    if mine:
        summary += f" My own suggestions here: {_join(mine)}."
    return {
        "text": " ".join(part for part in (reply, summary) if part),
        "moves": moves,
    }
