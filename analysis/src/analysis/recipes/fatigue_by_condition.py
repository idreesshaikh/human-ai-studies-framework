"""fatigue-by-condition (RQ-P1): self-reported fatigue under AI assistance.

Test choice: fatigue probes are 1-5 Likert responses - ordinal, tiny n,
within-subjects design - so the comparison is the **exact Wilcoxon
signed-rank** on per-participant mean scores when participants have both
conditions, degrading to the **exact Mann-Whitney U** otherwise (both via
``analysis.stats.compare_by_condition``, which also carries the effect
size and per-cell n).
"""

from __future__ import annotations

from analysis import figures
from analysis.core import RecipeResult, recipe
from analysis.dataset import Dataset
from analysis.figures import condition_colors, new_axes
from analysis.recipes._common import compare_or_describe

METHODS = (
    "Fatigue probes are 1-5 Likert responses (`fatigue_response.score`). "
    "Scores are aggregated to one mean per (participant, condition) to avoid "
    "pseudo-replication, then compared with the exact two-sided Wilcoxon "
    "signed-rank test on participants observed in both conditions "
    "(matched-pairs rank-biserial correlation as effect size); when fewer "
    "than two participants have both conditions the exact two-sided "
    "Mann-Whitney U with Cliff's delta is used on the unpaired cells. "
    "Per-cell n is reported with every statistic; at pilot sample sizes all "
    "results are hypothesis-generating."
)


@recipe(
    id="fatigue-by-condition",
    answers=["RQ-P1"],
    requires_events=["fatigue_response"],
    title="Self-reported fatigue by condition",
)
def run(dataset: Dataset) -> RecipeResult:
    df = dataset.of_type("fatigue_response")
    test, cells, sentence = compare_or_describe(df, "score", dataset)

    # Trajectories: score over minutes-into-session, one line per session.
    spans = dataset.session_spans.set_index("sessionId")
    traj = df.join(spans["start"], on="sessionId")
    traj["minute"] = (traj["ts"] - traj["start"]).dt.total_seconds() / 60
    colors = condition_colors(dataset.conditions)
    fig, ax = new_axes(
        "Fatigue trajectories over the session",
        "minutes into session",
        "fatigue score (1-5)",
    )
    for (sid, cond), g in traj.groupby(["sessionId", "condition"]):
        g = g.sort_values("minute")
        ax.plot(
            g["minute"],
            g["score"],
            marker="o",
            markersize=4.5,
            markeredgecolor=figures.SURFACE,
            markeredgewidth=1,
            linewidth=1.4,
            color=colors[cond],
            label=f"{sid} ({cond})",
        )
    ax.set_ylim(0, 5.4)
    ax.legend(fontsize=7, frameon=False, labelcolor=figures.SECONDARY)
    fig.tight_layout()

    strip = figures.strip_by_condition(
        df,
        "score",
        dataset.conditions,
        "Fatigue responses by condition",
        "fatigue score (1-5)",
        unit_label="response",
    )

    tables = {"per_condition": cells, "responses": df.drop(columns=["seq"])}
    if test:
        import pandas as pd

        tables["test"] = pd.DataFrame([test.row()])

    return RecipeResult(
        tables=tables,
        figures={"trajectories": fig, "by_condition": strip},
        summary=f"Self-reported fatigue (RQ-P1). {sentence}",
        methods=METHODS,
    )
