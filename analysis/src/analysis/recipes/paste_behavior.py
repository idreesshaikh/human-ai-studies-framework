"""paste-behavior (RQ-P3): paste size and frequency by condition.

Test choice: paste sizes are heavily right-skewed character counts and
paste rates are small counts over unequal time bases, so both use the
exact nonparametric machinery of ``analysis.stats`` (Wilcoxon paired /
Mann-Whitney U + Cliff's delta). Needs the behavioral leg.
"""

from __future__ import annotations

import pandas as pd

from analysis import figures
from analysis.core import RecipeResult, recipe
from analysis.dataset import Dataset
from analysis.recipes._common import compare_or_describe

METHODS = (
    "Each `clipboard_paste` event carries the pasted size in characters "
    "(never content - FR-ETH-2). Paste frequency is events per hour over "
    "each session's event span; paste size is compared at the event level "
    "with the caveat that pastes within one session are not independent "
    "(per-participant means drive the tests, via "
    "`analysis.stats.compare_by_condition`). Exact Wilcoxon signed-rank "
    "(paired per-participant means, rank-biserial effect size) or exact "
    "Mann-Whitney U (Cliff's delta) as available; per-cell n always "
    "reported; pilot-scale results are hypothesis-generating."
)


@recipe(
    id="paste-behavior",
    answers=["RQ-P3"],
    requires_events=["clipboard_paste"],
    title="Paste size and frequency by condition",
)
def run(dataset: Dataset) -> RecipeResult:
    pastes = dataset.of_type("clipboard_paste")
    pastes["charCount"] = pd.to_numeric(pastes["charCount"], errors="coerce")

    spans = dataset.session_spans
    per_session = spans.merge(
        pastes.groupby("sessionId", as_index=False).agg(pastes=("type", "count")),
        on="sessionId",
        how="left",
    ).fillna({"pastes": 0})
    per_session["pastesPerHour"] = per_session["pastes"] / (
        per_session["durationMinutes"] / 60
    ).clip(lower=1e-9)

    size_test, size_cells, size_sentence = compare_or_describe(
        pastes, "charCount", dataset
    )
    rate_test, rate_cells, rate_sentence = compare_or_describe(
        per_session, "pastesPerHour", dataset
    )

    size_fig = figures.strip_by_condition(
        pastes,
        "charCount",
        dataset.conditions,
        "Paste sizes by condition",
        "characters per paste",
        unit_label="paste",
    )
    rate_fig = figures.strip_by_condition(
        per_session,
        "pastesPerHour",
        dataset.conditions,
        "Paste frequency by condition",
        "pastes / hour",
        unit_label="session",
    )

    tables = {
        "per_session": per_session,
        "size_per_condition": size_cells,
        "rate_per_condition": rate_cells,
    }
    test_rows = [t.row() for t in (size_test, rate_test) if t]
    if test_rows:
        tables["tests"] = pd.DataFrame(test_rows)

    return RecipeResult(
        tables=tables,
        figures={"size_by_condition": size_fig, "rate_by_condition": rate_fig},
        summary=(
            f"Paste behavior (RQ-P3). Size: {size_sentence} Frequency: {rate_sentence}"
        ),
        methods=METHODS,
    )
