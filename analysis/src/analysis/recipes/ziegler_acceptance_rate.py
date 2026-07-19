"""ziegler-acceptance-rate (RQ-P4): a published paper's analysis as a
recipe - the FR-ANA-5 proof of concept that "papers become recipes".

Replicates the headline metric of:

    Ziegler, Kalliamvakou, Li, Rice, Rifkin, Simister, Sittampalam,
    Aftandilian. "Productivity Assessment of Neural Code Completion."
    MAPS '22 (arXiv:2205.06537), 2022.

Ziegler et al. measure **acceptance rate** - accepted completions divided
by shown completions - and show it is the telemetry measure that best
predicts developers' self-reported productivity (better than persistence
measures). Our `ai_suggestion` lifecycle events (`shown` ->
`accepted`/`dismissed`) carry exactly the numerator and denominator, per
session instead of per developer-week; where the paper aggregates over
weeks of Copilot telemetry, a lab session is our observation unit and the
condition split replaces their between-user comparison. Following the
paper's approach we also report the correlation of acceptance rate with
the session's self-reported measure (our fatigue mean stands in for their
productivity survey; the substitution is stated, not hidden).
"""

from __future__ import annotations

import pandas as pd

from analysis import figures, stats
from analysis.core import RecipeResult, recipe
from analysis.dataset import Dataset
from analysis.recipes._common import compare_or_describe

METHODS = (
    "Replication of Ziegler et al. (MAPS '22, arXiv:2205.06537): "
    "acceptance rate = accepted / shown `ai_suggestion` events, computed "
    "per session (the paper's unit is developer-weeks of Copilot "
    "telemetry; the metric definition is unchanged). Conditions are "
    "compared with the exact Wilcoxon/Mann-Whitney machinery (effect "
    "sizes, per-cell n). Where the paper correlates acceptance rate with "
    "self-reported productivity (Spearman), the pilot correlates it with "
    "the session's mean fatigue response - an explicit stand-in, reported "
    "as such. Pilot n is hypothesis-generating."
)


@recipe(
    id="ziegler-acceptance-rate",
    answers=["RQ-P4"],
    requires_events=["ai_suggestion"],
    title="Acceptance rate per Ziegler et al. 2022 (replication demo)",
)
def run(dataset: Dataset) -> RecipeResult:
    sug = dataset.of_type("ai_suggestion")
    per_session = (
        sug.assign(
            shown=(sug["action"] == "shown").astype(int),
            accepted=(sug["action"] == "accepted").astype(int),
        )
        .groupby(["sessionId", "participantId", "condition"], as_index=False)
        .agg(shown=("shown", "sum"), accepted=("accepted", "sum"))
    )
    per_session = per_session[per_session["shown"] > 0].copy()
    per_session["acceptanceRate"] = per_session["accepted"] / per_session["shown"]

    test, cells, sentence = compare_or_describe(per_session, "acceptanceRate", dataset)

    tables: dict[str, pd.DataFrame] = {
        "per_session": per_session,
        "per_condition": cells,
    }
    sentences = [
        f"Acceptance rate (Ziegler et al. 2022 metric): {sentence}",
    ]
    if test:
        tables["test"] = pd.DataFrame([test.row()])

    # The paper's second step: does the telemetry metric track the
    # self-report? (their productivity survey -> our fatigue mean).
    fatigue = dataset.of_type("fatigue_response")
    if not fatigue.empty:
        f_mean = fatigue.groupby("sessionId")["score"].mean().rename("fatigueMean")
        j = per_session.join(f_mean, on="sessionId").dropna(subset=["fatigueMean"])
        if len(j) >= 3:
            t = stats.spearman(
                j["acceptanceRate"].tolist(), j["fatigueMean"].tolist(), "sessions"
            )
            tables["rate_vs_fatigue_test"] = pd.DataFrame([t.row()])
            sentences.append(
                f"Acceptance rate vs mean fatigue (paper's survey stand-in): {t.line()}"
            )
        else:
            sentences.append(
                f"Rate-vs-self-report correlation needs >= 3 sessions with "
                f"both measures (have {len(j)})."
            )

    fig = figures.strip_by_condition(
        per_session,
        "acceptanceRate",
        dataset.conditions,
        "Suggestion acceptance rate per session (Ziegler et al. 2022)",
        "accepted / shown",
        unit_label="session",
    )

    return RecipeResult(
        tables=tables,
        figures={"acceptance_rate": fig},
        summary="Replication demo (RQ-P4). " + " ".join(sentences),
        methods=METHODS,
    )
