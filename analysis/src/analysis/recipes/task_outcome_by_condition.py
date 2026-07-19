"""task-outcome-by-condition (RQ-P1..P5 ground truth): acceptance-test
pass rates and time-to-first-green (needs's task harness).

Test choices: pass/fail counts per condition form a 2x2 table - **Fisher's
exact test** (the only honest choice at pilot counts) with the odds ratio.
Time-to-first-green is a skewed duration - exact Mann-Whitney U + Cliff's
delta (or Wilcoxon when paired, via ``analysis.stats``). The
outcome-conditioned splits of other legs' headline measures are reported
as descriptive tables only - splitting tiny cells twice is where p-values
go to lie.
"""

from __future__ import annotations

import pandas as pd

from analysis import figures, stats
from analysis.core import RecipeResult, recipe
from analysis.dataset import Dataset
from analysis.recipes._common import compare_or_describe, describe_cells

METHODS = (
    "`task_outcome` events carry the task harness's acceptance-test "
    "verdict (`passed`) and, when the run first turned green, "
    "`firstGreenMs` (fallback: elapsed time from session start to the "
    "first passing outcome). Pass rates by condition: Fisher's exact test "
    "on the 2x2 pass/fail table with the odds ratio. Time-to-first-green: "
    "exact Wilcoxon/Mann-Whitney machinery with effect sizes. "
    "Outcome-conditioned splits of fatigue and paste measures are "
    "descriptive only - no tests on twice-split pilot cells. Per-cell n "
    "everywhere; hypothesis-generating at pilot scale."
)


@recipe(
    id="task-outcome-by-condition",
    answers=["RQ-P1", "RQ-P2", "RQ-P3", "RQ-P4", "RQ-P5"],
    requires_events=["task_outcome"],
    title="Task outcomes: pass rates and time-to-first-green",
)
def run(dataset: Dataset) -> RecipeResult:
    outcomes = dataset.of_type("task_outcome")
    outcomes["passed"] = outcomes.get("passed", False).astype(bool)
    spans = dataset.session_spans.set_index("sessionId")

    # One verdict per session: the last outcome; first green for timing.
    last = outcomes.sort_values("ts").groupby("sessionId").tail(1).copy()

    def first_green_minutes(sid: str) -> float:
        g = outcomes[(outcomes["sessionId"] == sid) & outcomes["passed"]]
        if g.empty:
            return float("nan")
        row = g.sort_values("ts").iloc[0]
        ms = pd.to_numeric(row.get("firstGreenMs"), errors="coerce")
        if pd.notna(ms):
            return float(ms) / 60_000
        return (row["ts"] - spans.loc[sid, "start"]).total_seconds() / 60

    last["firstGreenMinutes"] = [first_green_minutes(s) for s in last["sessionId"]]

    tables: dict[str, pd.DataFrame] = {"per_session": last}
    sentences = []
    figs = {}

    # Pass rate x condition (Fisher exact when 2 conditions).
    rate = (
        last.groupby("condition")["passed"].agg(n="count", passed="sum").reset_index()
    )
    rate["passRate"] = rate["passed"] / rate["n"]
    tables["pass_rates"] = rate
    conds = [c for c in dataset.conditions if c in set(rate["condition"])]
    if len(conds) >= 2:
        cell = rate.set_index("condition")
        table = [
            [int(cell.loc[c, "passed"]), int(cell.loc[c, "n"] - cell.loc[c, "passed"])]
            for c in conds[:2]
        ]
        t = stats.fisher_2x2(
            table,
            cells={c: int(cell.loc[c, "n"]) for c in conds[:2]},
            note="rows: condition; columns: passed/failed sessions",
        )
        tables["pass_rate_test"] = pd.DataFrame([t.row()])
        sentences.append(f"Pass rates: {t.line()}")
    else:
        sentences.append(
            "Pass rates: one condition present - "
            + ", ".join(
                f"{r.condition}: {int(r.passed)}/{int(r.n)}" for r in rate.itertuples()
            )
            + " (descriptive only)."
        )

    # Time-to-first-green.
    greens = last.dropna(subset=["firstGreenMinutes"])
    if len(greens):
        ttg_test, ttg_cells, ttg_sentence = compare_or_describe(
            greens, "firstGreenMinutes", dataset
        )
        tables["first_green_per_condition"] = ttg_cells
        if ttg_test:
            tables["first_green_test"] = pd.DataFrame([ttg_test.row()])
        sentences.append(f"Time-to-first-green: {ttg_sentence}")
        figs["first_green"] = figures.strip_by_condition(
            greens,
            "firstGreenMinutes",
            dataset.conditions,
            "Time to first green by condition",
            "minutes to first passing test run",
            unit_label="session",
        )
    else:
        sentences.append("Time-to-first-green: no passing sessions yet.")

    # Outcome-conditioned splits (descriptive only, deliberately).
    verdicts = last.set_index("sessionId")["passed"]
    for measure, events, column in [
        ("fatigue", dataset.of_type("fatigue_response"), "score"),
        ("paste_size", dataset.of_type("clipboard_paste"), "charCount"),
    ]:
        if events.empty:
            continue
        joined = events.join(verdicts.rename("passed"), on="sessionId").dropna(
            subset=["passed"]
        )
        if joined.empty:
            continue
        verdict_label = joined["passed"].map({True: "passed", False: "failed"})
        split = (
            joined.drop(columns=["condition"])  # outcome plays the cell role
            .assign(outcome=verdict_label)
            .rename(columns={"outcome": "condition"})
        )
        tables[f"{measure}_by_outcome"] = describe_cells(split, column)

    return RecipeResult(
        tables=tables,
        figures=figs,
        summary="Task outcomes (ground truth). " + " ".join(sentences),
        methods=METHODS,
    )
