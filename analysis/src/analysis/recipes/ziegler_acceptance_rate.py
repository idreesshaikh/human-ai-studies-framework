"""Captured inline-suggestion accept counts; no reliable display denominator."""

from __future__ import annotations

import pandas as pd

from analysis.core import RecipeResult, recipe
from analysis.dataset import Dataset

METHODS = (
    "TERN records accepted inline-suggestion keybindings, but the public VS Code "
    "API does not expose a reliable count of displayed suggestions. The legacy "
    "`shown` action records an inline-provider query, not a displayed suggestion. "
    "Therefore this recipe reports captured accept counts only and does not "
    "calculate an acceptance rate or compare rates across conditions. Counts "
    "are a lower bound on inline-suggestion use and omit other AI surfaces."
)


@recipe(
    id="ziegler-acceptance-rate",
    answers=["RQ-P4"],
    requires_events=["ai_suggestion"],
    title="Captured inline-suggestion accept counts",
)
def run(dataset: Dataset) -> RecipeResult:
    suggestions = dataset.of_type("ai_suggestion")
    columns = ["sessionId", "participantId", "condition", "acceptedEvents"]

    if suggestions.empty or "action" not in suggestions:
        per_session = pd.DataFrame(columns=columns)
    else:
        accepted = suggestions.assign(
            acceptedEvents=(suggestions["action"] == "accepted").astype(int)
        )
        per_session = accepted.groupby(
            ["sessionId", "participantId", "condition"], as_index=False
        )["acceptedEvents"].sum()

    if per_session.empty:
        per_condition = pd.DataFrame(
            columns=["condition", "sessionCount", "acceptedEvents"]
        )
        accepted_total = 0
    else:
        per_condition = per_session.groupby("condition", as_index=False).agg(
            sessionCount=("sessionId", "nunique"),
            acceptedEvents=("acceptedEvents", "sum"),
        )
        accepted_total = int(per_session["acceptedEvents"].sum())

    return RecipeResult(
        tables={"per_session": per_session, "per_condition": per_condition},
        summary=(
            f"Captured {accepted_total} inline-suggestion accept event(s). "
            "No acceptance rate is reported because TERN cannot reliably "
            "observe the number of suggestions displayed."
        ),
        methods=METHODS,
    )
