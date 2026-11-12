"""Descriptive counts of captured inline-suggestion keybinding actions."""

from __future__ import annotations

import pandas as pd

from analysis.core import RecipeResult, recipe
from analysis.dataset import Dataset

METHODS = (
    "Reports captured accept and dismiss keybinding events by session and "
    "condition. The public VS Code API does not expose a reliable count of "
    "displayed suggestions or their visibility duration, so this recipe does "
    "not estimate acceptance rates or review latency. Legacy `shown` events "
    "are provider-query proxies and are excluded from use counts. Keybinding "
    "events also miss partial accepts, mouse actions and typing-through."
)


@recipe(
    id="ai-review-behavior",
    answers=["RQ-P4"],
    requires_events=["ai_suggestion"],
    title="Captured inline-suggestion actions",
)
def run(dataset: Dataset) -> RecipeResult:
    suggestions = dataset.of_type("ai_suggestion")
    columns = [
        "sessionId",
        "participantId",
        "condition",
        "acceptedEvents",
        "dismissedEvents",
        "legacyQueryProxyEvents",
    ]

    if suggestions.empty or "action" not in suggestions:
        per_session = pd.DataFrame(columns=columns)
    else:
        classified = suggestions.assign(
            acceptedEvents=(suggestions["action"] == "accepted").astype(int),
            dismissedEvents=(suggestions["action"] == "dismissed").astype(int),
            legacyQueryProxyEvents=suggestions["action"]
            .isin(["shown", "queried"])
            .astype(int),
        )
        per_session = classified.groupby(
            ["sessionId", "participantId", "condition"], as_index=False
        )[columns[3:]].sum()

    if per_session.empty:
        per_condition = pd.DataFrame(
            columns=["condition", "sessionCount", *columns[3:]]
        )
        accepted_total = dismissed_total = 0
    else:
        per_condition = per_session.groupby("condition", as_index=False).agg(
            sessionCount=("sessionId", "nunique"),
            acceptedEvents=("acceptedEvents", "sum"),
            dismissedEvents=("dismissedEvents", "sum"),
            legacyQueryProxyEvents=("legacyQueryProxyEvents", "sum"),
        )
        accepted_total = int(per_session["acceptedEvents"].sum())
        dismissed_total = int(per_session["dismissedEvents"].sum())

    return RecipeResult(
        tables={"per_session": per_session, "per_condition": per_condition},
        summary=(
            f"Captured {accepted_total} inline-suggestion accept and "
            f"{dismissed_total} dismiss keybinding event(s). These are "
            "incomplete counts of observed interactions, not total AI use."
        ),
        methods=METHODS,
    )
