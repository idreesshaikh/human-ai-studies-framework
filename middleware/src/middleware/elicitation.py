"""How the design conversation listens before it proposes."""

from __future__ import annotations

import re

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
    "programming",
    # A task named by its language is a software task even without "code".
    "javascript",
    "typescript",
    "python",
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
    "inline suggestion actions",
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


FACETS: dict[str, dict] = {
    "population": {
        "label": "who takes part",
        "cues": (
            "developer",
            "developers",
            "engineer",
            "engineers",
            "student",
            "students",
            "participant",
            "participants",
            "professional",
            "practitioner",
            "practitioners",
            "junior",
            "senior",
            "novice",
            "expert",
            "team",
            "teams",
            "colleague",
            "colleagues",
            "volunteer",
            "programmer",
            "programmers",
            "intern",
            "interns",
            "employee",
            "employees",
            "people who",
            "n=",
            "recruit",
        ),
        "question": "Who takes part, and roughly how many can you realistically get?",
    },
    "task": {
        "label": "what they do",
        "cues": (
            "task",
            "tasks",
            "write",
            "writing",
            "implement",
            "refactor",
            "debug",
            "review",
            "maintenance",
            "feature",
            "bug",
            "exercise",
            "assignment",
            "problem",
            "codebase",
            "repository",
            "repo",
            "pull request",
            "issue",
            "ticket",
            "work on",
            "build",
            "fix",
        ),
        "question": "Which task will they actually be doing, and on whose code?",
    },
    "comparison": {
        "label": "what is compared",
        "cues": (
            "compare",
            "compared",
            "comparison",
            "versus",
            " vs ",
            "with and without",
            "without",
            "condition",
            "conditions",
            "control",
            "baseline",
            "arm",
            "arms",
            "group",
            "groups",
            "before and after",
            "treatment",
            "intervention",
            "between",
            "within",
            "instead of",
            "against",
        ),
        "question": (
            "What are you comparing: two ways of working, before and after, "
            "or is this a single-condition description?"
        ),
    },
    "outcome": {
        "label": "what is measured",
        "cues": (
            "measure",
            "measures",
            "measuring",
            "outcome",
            "time",
            "speed",
            "duration",
            "quality",
            "correctness",
            "defect",
            "defects",
            "bug",
            "error",
            "errors",
            "accuracy",
            "productivity",
            "effort",
            "workload",
            "satisfaction",
            "trust",
            "confidence",
            "perception",
            "complexity",
            "readability",
            "acceptance",
            "rate",
            "how long",
            "how many",
            "how well",
            "score",
        ),
        "question": "What would count as a result, and what do you want to measure?",
    },
    "constraints": {
        "label": "what is possible",
        "cues": (
            "lab",
            "field",
            "remote",
            "in person",
            "in-person",
            "session",
            "sessions",
            "minutes",
            "hour",
            "hours",
            "week",
            "weeks",
            "month",
            "months",
            "telemetry",
            "logs",
            "log data",
            "existing data",
            "github",
            "mining",
            "dataset",
            "archive",
            "ethics",
            "consent",
            "irb",
            "approval",
            "company",
            "internal",
            "production",
            "customer",
            "cannot",
            "can't",
            "constraint",
            "limited",
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


# The researcher profiles the conversation settings offer.
PROFILES: dict[str, dict] = {
    "student": {
        "label": "Student",
        "description": "Learning research methods; this may be a first study.",
    },
    "new-researcher": {
        "label": "New researcher",
        "description": "Research training, first empirical studies in this area.",
    },
    "experienced": {
        "label": "Experienced researcher",
        "description": "Designs and runs empirical studies regularly.",
    },
    "industry": {
        "label": "Industry practitioner",
        "description": "Studying developers inside a company (e.g. a platform team).",
    },
}

DEFAULT_PROFILE = "new-researcher"


# How much the assistant drives the conversation. Only "checks" changes what a
# turn may do: it answers and proposes nothing.
STEER_LEVELS: dict[str, dict] = {
    "leads": {"label": "Leads"},
    "guides": {"label": "Guides"},
    "assists": {"label": "Assists"},
    "checks": {"label": "Checks"},
}

# What the conversation assumes when the dial has never been moved.
DEFAULT_STEER = "leads"


def proposals_permitted(steer: str | None) -> bool:
    """Whether this level may carry design proposals at all."""
    return (steer if steer in STEER_LEVELS else DEFAULT_STEER) != "checks"


def profile_catalog() -> list[dict]:
    """Return the profiles exposed by the conversation settings UI."""
    return [
        {"id": key, "label": spec["label"], "description": spec["description"]}
        for key, spec in PROFILES.items()
    ]
