"""stuck-episodes (RQ-P1): frequency and duration of stuck episodes.

Test choice: episode rates (episodes per hour) and durations (minutes of
accumulated evidence) are skewed, tiny-n quantities, so both comparisons
use the exact nonparametric machinery of ``analysis.stats`` (Wilcoxon on
per-participant means when paired, Mann-Whitney U + Cliff's delta
otherwise). Rates are normalized by session span so unequal session
lengths cannot masquerade as condition effects.
"""

from __future__ import annotations

import pandas as pd

from analysis import figures
from analysis.core import RecipeResult, recipe
from analysis.dataset import Dataset
from analysis.recipes._common import compare_or_describe

METHODS = (
    "A stuck episode is one `stuck_response` event; its duration is the "
    "detector's accumulated evidence (`evidenceMs`). Episode counts are "
    "normalized to episodes per hour using each session's event span (an "
    "upper bound on active time; idle-corrected denominators arrive with "
    "the agent leg). Rates and durations are compared per condition with "
    "the exact Wilcoxon signed-rank on per-participant means (paired) or "
    "the exact Mann-Whitney U with Cliff's delta (unpaired); per-cell n "
    "accompanies every statistic and pilot-scale results are "
    "hypothesis-generating."
)


@recipe(
    id="stuck-episodes",
    answers=["RQ-P1"],
    requires_events=["stuck_response"],
    title="Stuck episodes: frequency and duration by condition",
)
def run(dataset: Dataset) -> RecipeResult:
    episodes = dataset.of_type("stuck_response")
    episodes["durationMinutes"] = (
        pd.to_numeric(episodes.get("evidenceMs"), errors="coerce") / 60_000
    )

    spans = dataset.session_spans
    per_session = (
        episodes.groupby(
            ["sessionId", "participantId", "condition"], as_index=False
        )
        .agg(episodes=("type", "count"), stuckMinutes=("durationMinutes", "sum"))
        .merge(spans[["sessionId", "durationMinutes"]], on="sessionId")
    )
    # Sessions with zero episodes still count - join against all sessions.
    all_sessions = spans.merge(
        per_session[["sessionId", "episodes", "stuckMinutes"]],
        on="sessionId",
        how="left",
    ).fillna({"episodes": 0, "stuckMinutes": 0.0})
    all_sessions["episodesPerHour"] = all_sessions["episodes"] / (
        all_sessions["durationMinutes"] / 60
    ).clip(lower=1e-9)

    rate_test, rate_cells, rate_sentence = compare_or_describe(
        all_sessions, "episodesPerHour", dataset
    )
    dur_test, dur_cells, dur_sentence = compare_or_describe(
        episodes, "durationMinutes", dataset
    )

    fig = figures.strip_by_condition(
        all_sessions,
        "episodesPerHour",
        dataset.conditions,
        "Stuck episodes per hour by condition",
        "episodes / hour",
        unit_label="session",
    )
    dur_fig = figures.strip_by_condition(
        episodes,
        "durationMinutes",
        dataset.conditions,
        "Stuck episode durations by condition",
        "accumulated evidence (minutes)",
        unit_label="episode",
    )

    tables = {
        "per_session": all_sessions,
        "rate_per_condition": rate_cells,
        "duration_per_condition": dur_cells,
    }
    test_rows = [t.row() for t in (rate_test, dur_test) if t]
    if test_rows:
        tables["tests"] = pd.DataFrame(
            test_rows, index=["episodesPerHour", "durationMinutes"][: len(test_rows)]
        )

    return RecipeResult(
        tables=tables,
        figures={"rate_by_condition": fig, "duration_by_condition": dur_fig},
        summary=(
            "Stuck episodes (RQ-P1). "
            f"Rate: {rate_sentence} Duration: {dur_sentence}"
        ),
        methods=METHODS,
    )
