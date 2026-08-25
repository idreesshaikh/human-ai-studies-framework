"""How the design conversation listens before it proposes (FR-CONV-9/10)."""

from __future__ import annotations

import re

# Deliberately about interrogating the platform's own last move, not general curiosity.
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

# A low-information reply is a request for scaffolding, not another turn of the
# same elicitation question. Keep this deliberately narrow: a researcher saying
# "I don't know why" is still asking about the preceding proposal, while "I don't
# know" or "what?" needs the platform to explain the choice in plain language.
_STUCK_EXACT = frozenset(
    {
        "what",
        "huh",
        "i don't know",
        "i dont know",
        "not sure",
        "im not sure",
        "i'm not sure",
        "no idea",
        "i'm lost",
        "im lost",
        "ok",
        "okay",
        "sure",
        "yes",
        "exactly",
        "same thing",
        "exactly the same thing",
        "yes indeed",
        "yes absolutely",
        "what else",
        "what else do you need",
        "i've a sample example",
        "ive a sample example",
        "i have a sample example",
        "that shouldn't matter to you",
        "that shouldnt matter to you",
    }
)
_STUCK_PHRASES = (
    "help me",
    "can you help",
    "i don't understand",
    "i dont understand",
    "i'm confused",
    "im confused",
    "sample example",
)

# PHOENIX is intentionally a study-instrumentation product, not a general
# research-methods assistant. Keep the boundary narrow enough to be useful: a
# student who is programming is a valid participant, while a study outside
# software development is not. This check runs before retrieval or the model so
# an unsupported idea cannot fall into the normal elicitation loop.
_OUT_OF_SCOPE_CUES = (
    "exam",
    "exams",
    "midterm",
    "midterms",
    "final exam",
    "coursework",
    "course work",
    "classroom",
    "lecture",
    "lectures",
    "grading",
    "grade",
    "grades",
    "academic performance",
    "learning outcome",
    "learning outcomes",
    "patient",
    "patients",
    "clinical",
    "healthcare",
    "medical",
    "treatment",
    "therapy",
    "customer satisfaction",
    "customer journey",
    "support journey",
    "marketing",
    "sales",
    "election",
    "political campaign",
    "social media",
    "consumer behavior",
)

_SUPPORTED_STUDY_CUES = (
    "code",
    "coding",
    "software",
    "developer",
    "developers",
    "engineer",
    "engineers",
    "engineering",
    "programmer",
    "programmers",
    "debug",
    "debugging",
    "bug",
    "bugs",
    "repository",
    "repo",
    "github",
    "pull request",
    "code review",
    "ai coding",
    "coding assistant",
    "copilot",
    "vs code",
    "vscode",
    "workspace snapshot",
    "workspace snapshots",
    "telemetry",
    "instrument",
    "capture",
    "review latency",
    "ai-generated code",
    "ai assistant",
)


def classify_scope(researcher_texts: list[str]) -> str:
    """Classify whether an idea belongs to PHOENIX's supported study family.

    ``student`` is deliberately not an out-of-scope cue on its own. Students
    can participate in a developer study. The education cues only block when
    the idea contains no software-development signal, which leaves room for a
    programming course study to stay in the supported lane.
    """
    corpus = " ".join(t.lower() for t in researcher_texts if t)
    outside = any(cue in corpus for cue in _OUT_OF_SCOPE_CUES)
    supported = any(cue in corpus for cue in _SUPPORTED_STUDY_CUES)
    if supported:
        return "supported"
    if outside:
        return "out-of-scope"
    return "unknown"


def needs_scaffolding(text: str) -> bool:
    """Whether the researcher has asked for help instead of adding study detail."""
    q = re.sub(r"\s+", " ", (text or "").strip().lower()).strip(" .!?…")
    if not q or any(cue in q for cue in _FOLLOWUP_CUES):
        return False
    return q in _STUCK_EXACT or any(phrase in q for phrase in _STUCK_PHRASES)

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
    """Whether the researcher's own words name a specific design shape."""
    q = (text or "").lower()
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", q)
        for signature in signatures
        for phrase in (signature or [])
        if phrase
    )


def classify_turn(text: str) -> str:
    """Classify a turn as follow-up, stuck, design request, or description."""
    q = (text or "").strip().lower()
    if not q:
        return "describe"
    if needs_scaffolding(q):
        return "needs-scaffolding"
    if any(cue in q for cue in _FOLLOWUP_CUES):
        return "followup-question"
    if any(pattern.search(q) for pattern in _DESIGN_REQUEST_PATTERNS):
        return "design-request"
    return "describe"


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

# How many facets must be on the table before the platform *volunteers* a design shape.
READY_FOR_DESIGN_FACETS = 3

DESIGN_ON_REQUEST_FACETS = 2


def assess_understanding(researcher_texts: list[str]) -> dict[str, bool]:
    """Which facets the researcher's own words have covered so far."""
    corpus = " ".join(t.lower() for t in researcher_texts if t)
    return {
        facet: any(
            re.search(rf"(?<![a-z]){re.escape(cue.strip())}(?![a-z])", corpus)
            if cue.strip().isalpha()
            else cue in corpus
            for cue in spec["cues"]
        )
        for facet, spec in FACETS.items()
    }


def is_complete_brief(text: str) -> bool:
    """Whether one message contains enough detail for a batch protocol pass.

    The normal conversation can still teach one choice at a time. A researcher
    who pastes a proper brief should not be forced back through that sequence,
    though. A substantial note with three of the five setup facets is enough to
    extract the explicit facts in one response while leaving genuinely missing
    details open. The length guard keeps a short answer such as "developers use
    AI" from being mistaken for a complete brief.
    """
    if not text or len(text.strip()) < 40:
        return False
    understanding = assess_understanding([text])
    known = sum(understanding.values())
    return known >= 4 or (known >= 3 and len(text.strip()) >= 80)


def missing_facets(understanding: dict[str, bool]) -> list[str]:
    """Facets still unknown, in the order they are worth asking about."""
    return [facet for facet in FACETS if not understanding.get(facet)]


def ready_for_design(
    understanding: dict[str, bool], *, requested: bool = False
) -> bool:
    """Whether enough of the idea is understood to name a design shape."""
    known = sum(1 for is_known in understanding.values() if is_known)
    return known >= (DESIGN_ON_REQUEST_FACETS if requested else READY_FOR_DESIGN_FACETS)


def next_question(understanding: dict[str, bool]) -> str:
    """The single most useful thing to ask next, or "" when nothing is missing."""
    missing = missing_facets(understanding)
    return FACETS[missing[0]]["question"] if missing else ""


def _fact_move(
    kind: str,
    target: str,
    proposal: str,
    patch: dict,
) -> dict:
    """Describe a fact the researcher stated plainly enough to record safely.

    This deliberately returns the wire-independent move shape rather than importing
    ``design_assistant.ProposedMove``. Elicitation is the lower-level listener and
    must stay free of the assistant module's types.
    """
    return {
        "kind": kind,
        "target": target,
        "proposal": proposal,
        "patch": patch,
        "refs": (),
    }


def _condition_pair(text: str) -> list[str] | None:
    """Recognise the common AI-vs-unassisted comparison without asking the model."""
    q = re.sub(r"\s+", " ", text.lower()).strip()
    assisted = bool(
        re.search(
            r"\b(?:ai[- ]assisted|with ai|using ai|ai assistance|with an ai|copilot)\b",
            q,
        )
    )
    unassisted = bool(
        re.search(
            r"\b(?:unassisted|non[- ]ai|unaided|without ai|without an ai|"
            r"with no ai|no ai|not using ai|without one)\b",
            q,
        )
    )
    # "only AI" is a single-condition statement, not evidence of the comparison
    # the product supports. Do not manufacture the missing control arm.
    only_assisted = bool(re.search(r"\bonly\s+(?:use\s+)?ai\b", q))
    if assisted and unassisted and not only_assisted:
        return ["ai-assisted", "unassisted"]

    if (
        re.search(r"\b(?:control|experimental)\s+(?:condition|group|arm)", q)
        and re.search(r"\bcontrol\b", q)
        and re.search(r"\bexperimental\b", q)
    ):
        return ["experimental", "control"]
    return None


def _task_fact(text: str) -> tuple[str, str] | None:
    """Extract a concrete coding task, keeping the capture conservative."""
    q = re.sub(r"\s+", " ", text.strip()).strip(" .!?;,")
    patterns = (
        re.compile(
            r"\b(?:fix|debug|repair)(?:ing)?\s+(?:a|an|the|one|their|this)?\s*"
            r"((?:[a-z0-9+#.-]+\s+){0,5}(?:bug|defect|issue|error|function|module|"
            r"code|codebase|repository))\b",
            re.I,
        ),
        re.compile(
            r"\b((?:small\s+)?bug[- ]fixing\s+task|code[- ]review\s+task|"
            r"refactor(?:ing)?\s+(?:a|an|the)?\s*[^,.!?;]{2,60})\b",
            re.I,
        ),
    )
    match = next((pattern.search(q) for pattern in patterns if pattern.search(q)), None)
    if not match:
        return None
    detail = re.sub(r"\s+", " ", match.group(1)).strip(" .!?;,")
    detail = re.split(
        r"\s+(?:with|without|using|during|while|and\s+(?:measure|time|record))\b",
        detail,
        maxsplit=1,
        flags=re.I,
    )[0].strip(" .!?;,")
    if len(detail) < 3:
        return None
    verb = "Debug" if re.match(r"debug", q, re.I) else "Fix"
    if detail.lower().startswith(("bug-fixing", "code-review", "refactor")):
        title = detail
    else:
        title = f"{verb} {detail}"
    return title, q


def explicit_protocol_facts(text: str) -> list[dict]:
    """Turn unambiguous researcher statements into reviewable protocol moves.

    The model remains responsible for methodological judgement. This listener only
    records facts the researcher already supplied, so a prose-only model response
    cannot make the conversation forget a task, comparison, design, or measure.
    """
    if not text or not text.strip():
        return []
    q = re.sub(r"\s+", " ", text.strip()).strip()
    lower = q.lower()
    moves: list[dict] = []

    conditions = _condition_pair(q)
    if conditions:
        moves.append(
            _fact_move(
                "set-parameter",
                "conditions[]",
                "Compare AI-assisted work with unassisted work.",
                {"section": "conditions", "op": "append", "value": conditions},
            )
        )

    if re.search(
        r"\bwithin[- ]subjects?\b|\bwithin subject\b|\bcross[- ]over\b|\bcrossover\b",
        lower,
    ):
        moves.append(
            _fact_move(
                "set-field",
                "participants.design",
                (
                    "Use a within-subjects design where each participant "
                    "completes both conditions."
                ),
                {
                    "op": "set-field",
                    "path": ["participants", "design"],
                    "value": "within-subjects",
                },
            )
        )
    elif re.search(r"\bbetween[- ]subjects?\b|\bbetween subject\b", lower):
        moves.append(
            _fact_move(
                "set-field",
                "participants.design",
                (
                    "Use a between-subjects design where each participant "
                    "completes one condition."
                ),
                {
                    "op": "set-field",
                    "path": ["participants", "design"],
                    "value": "between-subjects",
                },
            )
        )

    if re.search(r"\bcounter[- ]?balanc", lower):
        moves.append(
            _fact_move(
                "set-field",
                "participants.counterbalanced",
                "Counterbalance the order of conditions across participants.",
                {
                    "op": "set-field",
                    "path": ["participants", "counterbalanced"],
                    "value": True,
                },
            )
        )

    duration = re.search(r"\b(\d{1,3})\s*[- ]?minutes?\b", lower)
    if duration and re.search(r"\b(?:session|lab|study|experiment)\b", lower):
        minutes = int(duration.group(1))
        if 1 <= minutes <= 480:
            moves.append(
                _fact_move(
                    "set-field",
                    "session.durationMinutes",
                    f"Run each session for {minutes} minutes.",
                    {
                        "op": "set-field",
                        "path": ["session", "durationMinutes"],
                        "value": minutes,
                    },
                )
            )

    participant_count = re.search(
        r"\b(\d{1,4})\s+(?:participants?|developers?|engineers?|people|subjects?)\b",
        lower,
    )
    if participant_count:
        moves.append(
            _fact_move(
                "set-field",
                "participants.planned",
                f"Plan for {participant_count.group(1)} participants.",
                {
                    "op": "set-field",
                    "path": ["participants", "planned"],
                    "value": int(participant_count.group(1)),
                },
            )
        )

    task = _task_fact(q)
    if task:
        title, description = task
        moves.append(
            _fact_move(
                "declare-task",
                "tasks[]",
                f"Record the coding task as {title}.",
                {
                    "title": title,
                    "description": f"Researcher-described task: {description}.",
                },
            )
        )

    population = re.search(
        r"\b((?:novice|junior|senior|professional|student|experienced)\s+"
        r"(?:developers?|engineers?|programmers?))\b",
        lower,
    )
    if population:
        value = population.group(1)
        moves.append(
            _fact_move(
                "set-parameter",
                "participants[]",
                f"Recruit {value} as the study population.",
                {"section": "participants", "op": "append", "value": value},
            )
        )

    measure_terms = (
        ("cognitive load", "cognitive load"),
        ("mental workload", "mental workload"),
        ("code comprehension", "code comprehension"),
        ("task completion time", "task completion time"),
        ("task time", "task time"),
        ("correctness", "solution correctness"),
        ("substantive defects", "substantive defects"),
        ("review quality", "review quality"),
    )
    measures = [label for cue, label in measure_terms if cue in lower]
    if measures:
        moves.append(
            _fact_move(
                "add-measure",
                "measures[]",
                "Measure " + ", ".join(measures) + ".",
                {"section": "measures", "op": "append", "value": measures},
            )
        )

    # Keep one deterministic card per protocol target. A brief often says "within
    # subjects" and "crossover" together, which should not create two identical cards.
    unique: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for move in moves:
        patch = move["patch"]
        key = (move["kind"], repr(patch))
        if key not in seen:
            seen.add(key)
            unique.append(move)
    return unique


def understanding_summary(understanding: dict[str, bool]) -> dict:
    """
    The wire shape the UI and the turn payload carry: honest about what the platform
    does and doesn't yet know.
    """
    missing = missing_facets(understanding)
    return {
        "facets": {f: bool(understanding.get(f)) for f in FACETS},
        "known": [f for f in FACETS if understanding.get(f)],
        "missing": missing,
        "missingLabels": [FACETS[f]["label"] for f in missing],
        "facetLabels": {f: FACETS[f]["label"] for f in FACETS},
        "readyForDesign": ready_for_design(understanding),
        "facetsNeeded": READY_FOR_DESIGN_FACETS,
        # Naming what is missing without naming what will be asked is what made the
        # conversation feel open-ended: two reviewers asked, in different words, for a
        # list of what they still had to provide.
        "nextQuestion": next_question(understanding),
    }


# The *method* never changes with the profile  -  the same designs, the same statistics,
# the same honesty about threats.
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

DEFAULT_PROFILE = "new-researcher"


# The METHOD never changes with this level.
STEER_LEVELS: dict[str, dict] = {
    "leads": {
        "label": "Leads",
        "profile": "student",
        "guidance": (
            "DRIVE THIS CONVERSATION. Keep one useful next step visible, but "
            "do not turn the study into a questionnaire. Ask one question only "
            "when it is genuinely needed, accept 'not sure' as a deferral, and "
            "offer a conservative default with its assumption when that is safe. "
            "Do not force the prescribed order; the researcher can redirect, "
            "defer, or ask for literature at any time. Make it easy to overrule "
            "you."
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

# What the conversation assumes when the dial has never been moved: a visible next
# step with room to redirect, defer, or change the subject.
DEFAULT_STEER = "leads"


def steer_guidance(steer: str | None) -> str:
    """
    The prompt block for an steer level (falls back to the default for an unknown or
    absent one, never an empty instruction).
    """
    key = steer if steer in STEER_LEVELS else DEFAULT_STEER
    return STEER_LEVELS[key]["guidance"]


def steer_profile(steer: str | None) -> str | None:
    """The register an steer level implies, or None when the level is unknown."""
    spec = STEER_LEVELS.get(steer or "")
    return spec["profile"] if spec else None


def proposals_permitted(steer: str | None) -> bool:
    """Whether this level may carry design proposals at all."""
    return (steer if steer in STEER_LEVELS else DEFAULT_STEER) != "checks"


def steer_catalog() -> list[dict]:
    """The pickable steer levels, for the UI and for agents (FR-AGF)."""
    return [
        {"id": key, "label": spec["label"]} for key, spec in STEER_LEVELS.items()
    ]


def profile_guidance(profile: str | None) -> str:
    """
    The prompt block for a researcher profile (falls back to the default for an unknown
    or absent one, never an empty instruction).
    """
    key = profile if profile in PROFILES else DEFAULT_PROFILE
    return PROFILES[key]["guidance"]


def profile_catalog() -> list[dict]:
    """The pickable profiles, for the UI and for agents (FR-AGF)."""
    return [
        {"id": key, "label": spec["label"], "description": spec["description"]}
        for key, spec in PROFILES.items()
    ]
