"""How the design conversation listens before it proposes (FR-CONV-9/10).

Three deterministic judgements the conversation needs on every turn, kept
here so they are testable on their own and identical with or without an LLM:

1. **What is this turn?** (:func:`classify_turn`) A researcher asking *"why
   did you propose that?"* wants an **answer**, not three fresh proposals.
   Answering a question with new suggestions is the conversational failure
   that reads as "it forgot what we were talking about", so the intent is
   classified in code and enforced in code, not left to a prompt.

2. **How much of the idea is actually understood?**
   (:func:`assess_understanding`) A study design is a *consequence* of who
   the participants are, what they do, what is compared, and what is
   measured. Proposing a template before those are on the table boxes the
   researcher into a shape chosen from almost nothing. So the design shape
   is withheld — and the missing facet asked about instead — until the
   conversation has earned it (:func:`ready_for_design`).

3. **Who is asking?** (:data:`PROFILES`) A first-year student, a researcher
   running their first study, a methodologist who does this monthly, and an
   engineer inside a company need genuinely different conversations: the
   same rigour, different vocabulary, pacing, and defaults. What differs is
   *how the platform talks*, never what counts as sound method.

Facet detection is keyword-based on purpose. It runs offline, costs nothing,
never fabricates, and is wrong in a safe direction: an unrecognised facet
means one more clarifying question, which is the behaviour this module
exists to encourage.
"""

from __future__ import annotations

import re

# ------------------------------------------------------------ turn intent

#: Cues that this turn is asking about something *already said* — the
#: "why did you give me this?" case. Deliberately about interrogating the
#: platform's own last move, not general curiosity.
_FOLLOWUP_CUES = (
    "why did you",
    "why do you",
    "why does",
    "why is that",
    "why this",
    "why that",
    "why not",
    "why",
    "what do you mean",
    "what does that mean",
    "explain",
    "justify",
    "how come",
    "on what basis",
    "where does that come from",
    "says who",
    "i asked",
    "you didn't answer",
    "you did not answer",
    "that's not what i asked",
    "answer my question",
    "what's the difference",
    "what is the difference",
    "how do you know",
)

#: The researcher explicitly asking to be given a design now. Matched by
#: pattern rather than fixed phrases, because "what design and statistics
#: should I use?" and "which template do you recommend?" are the same ask and
#: a literal phrase list misses both.
_DESIGN_REQUEST_PATTERNS = (
    re.compile(
        r"\b(what|which|recommend|suggest|propose|pick|choose|give me)\b"
        r"[^.?!]{0,60}?\b(design|template|study type|statistic|test)\b"
    ),
    re.compile(
        r"\b(just )?(give|tell) me (the|a|your)\b[^.?!]{0,30}\b(design|answer)\b"
    ),
    re.compile(r"\b(skip|stop) the questions\b"),
    re.compile(r"\bi (already )?know what i want\b"),
)


def names_a_design(text: str, signatures: list[list[str]]) -> bool:
    """Whether the researcher's own words name a specific design shape.

    The gate exists to stop the *platform* boxing a researcher into a design
    chosen from almost nothing. It was never meant to overrule a researcher
    who says "let's run a paired RCT", refusing to record a design they
    named themselves is obstinacy, not care. So a turn carrying a template's
    own curated ``designSignature`` vocabulary opens the gate, however little
    else is known.

    Reuses the repertoire's signatures rather than a second word list, so a
    design's vocabulary stays declared in exactly one place (FR-TPL).
    """
    q = (text or "").lower()
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", q)
        for signature in signatures
        for phrase in (signature or [])
        if phrase
    )


def classify_turn(text: str) -> str:
    """``"followup-question"`` | ``"design-request"`` | ``"describe"``.

    A follow-up question wins over a design request: "why did you pick that
    design?" is a demand for reasoning, not for another design.
    """
    q = (text or "").strip().lower()
    if not q:
        return "describe"
    if any(cue in q for cue in _FOLLOWUP_CUES):
        return "followup-question"
    if any(pattern.search(q) for pattern in _DESIGN_REQUEST_PATTERNS):
        return "design-request"
    return "describe"


# ------------------------------------------------------ understanding model

#: The facets of a study idea that a design shape actually follows from. Each
#: maps to the cues that show a researcher has told us about it, and to the
#: question to ask when they haven't.
FACETS: dict[str, dict] = {
    "population": {
        "label": "who takes part",
        "cues": (
            "developer", "developers", "engineer", "engineers", "student",
            "students", "participant", "participants", "professional",
            "practitioner", "practitioners", "junior", "senior", "novice",
            "expert", "team", "teams", "colleague", "colleagues", "volunteer",
            "programmer", "programmers", "intern", "interns", "employee",
            "employees", "people who", "n=", "recruit",
        ),
        "question": "Who takes part, and roughly how many can you realistically get?",
    },
    "task": {
        "label": "what they do",
        "cues": (
            "task", "tasks", "write", "writing", "implement", "refactor",
            "debug", "review", "maintenance", "feature", "bug", "exercise",
            "assignment", "problem", "codebase", "repository", "repo",
            "pull request", "issue", "ticket", "work on", "build", "fix",
        ),
        "question": "Which task will they actually be doing, and on whose code?",
    },
    "comparison": {
        "label": "what is compared",
        "cues": (
            "compare", "compared", "comparison", "versus", " vs ",
            "with and without", "without",
            "condition", "conditions", "control", "baseline", "arm", "arms",
            "group", "groups", "before and after", "treatment",
            "intervention", "between", "within", "instead of", "against",
        ),
        "question": (
            "What are you comparing: two ways of working, before and after, "
            "or is this a single-condition description?"
        ),
    },
    "outcome": {
        "label": "what is measured",
        "cues": (
            "measure", "measures", "measuring", "outcome", "time", "speed",
            "duration", "quality", "correctness", "defect", "defects", "bug",
            "error", "errors", "accuracy", "productivity", "effort",
            "workload", "satisfaction", "trust", "confidence", "perception",
            "complexity", "readability", "acceptance", "rate", "how long",
            "how many", "how well", "score",
        ),
        "question": "What would count as a result, and what do you want to measure?",
    },
    "constraints": {
        "label": "what is possible",
        "cues": (
            "lab", "field", "remote", "in person", "in-person", "session",
            "sessions", "minutes", "hour", "hours", "week", "weeks", "month",
            "months", "telemetry", "logs", "log data", "existing data",
            "github", "mining", "dataset", "archive", "ethics", "consent",
            "irb", "approval", "company", "internal", "production",
            "customer", "cannot", "can't", "constraint", "limited",
            "available",
        ),
        "question": (
            "What is practically possible for you: live instrumented sessions, "
            "or existing data you already have access to?"
        ),
    },
}

#: How many facets must be on the table before the platform *volunteers* a
#: design shape. Three of five is a real conversation's worth of
#: understanding — enough to choose responsibly, not so much that the
#: platform interrogates someone who already knows what they want.
READY_FOR_DESIGN_FACETS = 3

#: When the researcher explicitly asks to be given a design, the bar drops —
#: but not to zero. A design named from nothing is a guess dressed as
#: methodology, and the researcher would have to unpick it later; two facets
#: is the least from which a shape can honestly follow. Below that the
#: platform says what it needs before it can answer, rather than either
#: refusing or guessing.
DESIGN_ON_REQUEST_FACETS = 2


def assess_understanding(researcher_texts: list[str]) -> dict[str, bool]:
    """Which facets the researcher's own words have covered so far.

    Only the *researcher's* turns count: the platform mentioning "conditions"
    in a question it asked cannot make the platform better informed.
    """
    corpus = " ".join(t.lower() for t in researcher_texts if t)
    # Word-ish boundaries so "time" doesn't match inside "sometimes".
    return {
        facet: any(
            re.search(rf"(?<![a-z]){re.escape(cue.strip())}(?![a-z])", corpus)
            if cue.strip().isalpha()
            else cue in corpus
            for cue in spec["cues"]
        )
        for facet, spec in FACETS.items()
    }


def missing_facets(understanding: dict[str, bool]) -> list[str]:
    """Facets still unknown, in the order they are worth asking about."""
    return [facet for facet in FACETS if not understanding.get(facet)]


def ready_for_design(
    understanding: dict[str, bool], *, requested: bool = False
) -> bool:
    """Whether enough of the idea is understood to name a design shape.

    ``requested`` lowers the bar to :data:`DESIGN_ON_REQUEST_FACETS`: a
    researcher who asks outright is answered rather than interrogated — but a
    design from *nothing* stays refused, because that is a guess, and the
    conversation exists to keep the researcher out of a box they didn't
    choose.
    """
    known = sum(1 for is_known in understanding.values() if is_known)
    return known >= (DESIGN_ON_REQUEST_FACETS if requested else READY_FOR_DESIGN_FACETS)


def next_question(understanding: dict[str, bool]) -> str:
    """The single most useful thing to ask next, or "" when nothing is
    missing. One question at a time, a wall of them is an interrogation."""
    missing = missing_facets(understanding)
    return FACETS[missing[0]]["question"] if missing else ""


def understanding_summary(understanding: dict[str, bool]) -> dict:
    """The wire shape the UI and the turn payload carry: honest about what
    the platform does and doesn't yet know."""
    missing = missing_facets(understanding)
    return {
        "facets": {f: bool(understanding.get(f)) for f in FACETS},
        "known": [f for f in FACETS if understanding.get(f)],
        "missing": missing,
        "missingLabels": [FACETS[f]["label"] for f in missing],
        "readyForDesign": ready_for_design(understanding),
        "facetsNeeded": READY_FOR_DESIGN_FACETS,
    }


# ------------------------------------------------------- researcher profiles

#: Who the platform is talking to. The *method* never changes with the
#: profile — the same designs, the same statistics, the same honesty about
#: threats. What changes is register, how much is explained, and which
#: trade-offs are worth surfacing to this person.
PROFILES: dict[str, dict] = {
    "student": {
        "label": "Student",
        "description": "Learning research methods; this may be a first study.",
        "guidance": (
            "You are talking to a STUDENT who is still learning research "
            "methods. Define every methodological term the first time you use "
            "it, in one short clause ('within-subjects, each person does both "
            "conditions, so they are their own comparison'). Prefer one small, "
            "genuinely feasible study over an ambitious one; say plainly when "
            "something is beyond a course project's reach. Explain *why* a "
            "choice follows from what they told you, so they learn the "
            "reasoning and not just the answer. Never assume they know what a "
            "counterbalance, an effect size, or a confound is. Encouraging, "
            "never condescending, they are doing real research."
        ),
    },
    "new-researcher": {
        "label": "New researcher",
        "description": "Research training, first empirical studies in this area.",
        "guidance": (
            "You are talking to a RESEARCHER EARLY IN THEIR CAREER: they know "
            "what a hypothesis and a control condition are, but this design "
            "space (human-AI studies of developers) is new to them. Skip "
            "textbook definitions; do name the field-specific traps, the "
            "perception gap between felt and measured productivity, "
            "task-selection bias, why small-N within-subjects usually beats "
            "underpowered between-subjects here. Point at the papers that "
            "established each convention so they can read further, and be "
            "explicit about what the reviewers of this literature will ask."
        ),
    },
    "experienced": {
        "label": "Experienced researcher",
        "description": "Designs and runs empirical studies regularly.",
        "guidance": (
            "You are talking to an EXPERIENCED METHODOLOGIST. Be brief and "
            "peer-level: no definitions, no methodology tutorials, no "
            "reassurance. Lead with what is contested or non-obvious, the "
            "threat that is hard to mitigate here, where this corpus's "
            "conventions disagree, the specific power/effect-size problem at "
            "their n. Assume they will push back, and give them the reasoning "
            "to push back on. If their stated plan has a defensible "
            "alternative, name it and say what would decide between them."
        ),
    },
    "industry": {
        "label": "Industry practitioner",
        "description": "Studying developers inside a company (e.g. a platform team).",
        "guidance": (
            "You are talking to a PRACTITIONER INSIDE A COMPANY studying their "
            "own engineers. Respect the constraints that actually bind them: "
            "you usually cannot randomise people to conditions, participation "
            "competes with delivery pressure, telemetry may already exist "
            "while consent for it may not, and results have to survive being "
            "shown to management. Prefer designs that work under those "
            "constraints, within-subjects, pre/post around a rollout, "
            "quasi-experiments with named confounds, existing-telemetry "
            "analyses, and be explicit about what each one can and cannot "
            "claim. Treat employee consent and data handling as first-class, "
            "not paperwork. Speak in engineering-outcome terms (cycle time, "
            "review load, defect escape) as well as research ones."
        ),
    },
}

#: What the conversation assumes when nobody has said who they are: enough
#: explanation to be useful to a newcomer, without talking down to anyone.
DEFAULT_PROFILE = "new-researcher"


# --------------------------------------------------------------- steer level

#: How much the assistant DRIVES the conversation, as distinct from which
#: register it speaks in. The two are separate levers and the UI's one dial
#: moves both: a researcher who wants a quieter colleague is not asking to be
#: spoken to as a novice, and one who wants terms defined is not asking to be
#: led by the nose.
#:
#: The METHOD never changes with this level. The same designs, the same
#: statistics, the same honesty about what is grounded and what is not. What
#: changes is how much arrives unprompted — which is why the ``initiative``
#: block below is paired with a hard filter in ``design_assistant`` rather
#: than being left to the model's goodwill.
#:
#: ``profile`` is the register this level implies when the caller has not
#: declared one of their own; a declared profile always wins, because who you
#: are is an account fact and how much help you want right now is not.
STEER_LEVELS: dict[str, dict] = {
    "leads": {
        "label": "Leads",
        "profile": "student",
        "guidance": (
            "DRIVE THIS CONVERSATION. Ask exactly ONE question per turn, "
            "the single most useful thing you do not yet know, and then "
            "name the move you would make next yourself, with the reasoning "
            "that got you there. Do not present a menu of options and ask "
            "them to choose; choose, show your work, and make it easy to "
            "overrule you. Assume they would rather be shown a good default "
            "than be asked to arbitrate a decision they do not yet have the "
            "vocabulary for."
        ),
    },
    "guides": {
        "label": "Guides",
        "profile": "new-researcher",
        "guidance": (
            "PROPOSE FREELY, BUT FOLLOW THEIR ORDER. Put forward the moves "
            "the study needs and say why each one follows from what they "
            "told you, but take up the thread they raised rather than "
            "steering back to your own agenda. If they are working on "
            "measures, work on measures."
        ),
    },
    "assists": {
        "label": "Assists",
        "profile": "experienced",
        "guidance": (
            "PROPOSE ONLY WHERE THE PROTOCOL IS STRUCTURALLY INCOMPLETE. "
            "Answer what they actually asked, and add a proposal only when a "
            "required part of the protocol is missing or a stated plan will "
            "not support the claim they want to make. No proposals offered "
            "for completeness, no restating what they already decided."
        ),
    },
    "checks": {
        "label": "Checks",
        "profile": "experienced",
        "guidance": (
            "STAY OUT OF THE WAY. Answer exactly what was asked, at "
            "peer level, and nothing else. The ONLY thing you raise "
            "unprompted is a methodological risk: a threat to validity that "
            "would survive into the results, a statistical plan that cannot "
            "answer the stated question, or a claim you cannot ground in the "
            "corpus. Say those plainly and briefly. Everything else waits to "
            "be asked for."
        ),
    },
}

#: What the conversation assumes when the dial has never been moved: proposing
#: and explaining, without steering.
DEFAULT_STEER = "guides"


def steer_guidance(steer: str | None) -> str:
    """The prompt block for an steer level (falls back to the default for an
    unknown or absent one, never an empty instruction)."""
    key = steer if steer in STEER_LEVELS else DEFAULT_STEER
    return STEER_LEVELS[key]["guidance"]


def steer_profile(steer: str | None) -> str | None:
    """The register an steer level implies, or None when the level is
    unknown. A profile the caller declared themselves outranks this."""
    spec = STEER_LEVELS.get(steer or "")
    return spec["profile"] if spec else None


def proposals_permitted(steer: str | None) -> bool:
    """Whether this level may carry design proposals at all.

    The enforcement half of the dial. At ``checks`` the assistant answers and
    warns but does not propose, and that is applied to the moves themselves in
    :mod:`design_assistant` — a prompt can be ignored, this cannot.
    """
    return (steer if steer in STEER_LEVELS else DEFAULT_STEER) != "checks"


def steer_catalog() -> list[dict]:
    """The pickable steer levels, for the UI and for agents (FR-AGF)."""
    return [
        {"id": key, "label": spec["label"]} for key, spec in STEER_LEVELS.items()
    ]


def profile_guidance(profile: str | None) -> str:
    """The prompt block for a researcher profile (falls back to the default
    for an unknown or absent one, never an empty instruction)."""
    key = profile if profile in PROFILES else DEFAULT_PROFILE
    return PROFILES[key]["guidance"]


def profile_catalog() -> list[dict]:
    """The pickable profiles, for the UI and for agents (FR-AGF)."""
    return [
        {"id": key, "label": spec["label"], "description": spec["description"]}
        for key, spec in PROFILES.items()
    ]
