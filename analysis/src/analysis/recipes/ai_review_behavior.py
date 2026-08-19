"""ai-review-behavior (RQ-P4): how developers review AI code - the
differentiator recipe (no off-the-shelf tool computes it, because it joins
the AI-completion lifecycle, the viewport trace, edit provenance, and the
cognitive leg on one timeline).

Four analyses:

1. **Review latency, accept vs. not-accept** - `visibleMs` on the terminal
   `ai_suggestion` event. Exact Mann-Whitney U + Cliff's delta (latencies
   are skewed durations; the two outcome groups are independent by
   construction).
2. **Accept rate by suggestion size quartile** - schema v3 carries
   `charCount` only on *accepted* suggestions, so the honest computable
   variant is reported: the accepted-size distribution by quartile plus the
   overall accept rate, with the limitation stated in methods (a schema
   extension recording size at `shown` would complete it - that is an
   instrumentation finding, not something to paper over).
3. **Scroll coverage before commit-to-code** - for each AI-origin
   `edit_burst`, viewport dwell on the edited file in the following 60 s
   (visible-range spans joined by file and time). A dwell of ~0 s means
   code was accepted without being looked at.
4. **Review latency vs. most recent fatigue response** - each reviewed
   suggestion joined to the latest preceding `fatigue_response` on the
   shared timeline; Spearman rank correlation (monotone association, no
   linearity assumption at pilot n).
"""

from __future__ import annotations

import pandas as pd

from analysis import figures, stats
from analysis.core import RecipeResult, recipe
from analysis.dataset import Dataset
from analysis.figures import new_axes

METHODS = (
    "Suggestions are paired by `suggestionId`: a `shown` event and a "
    "terminal event (`accepted`/`dismissed`/`rejected`) whose `visibleMs` "
    "is the review latency. (1) Latency accept vs. not-accept: exact "
    "two-sided Mann-Whitney U with Cliff's delta. (2) Accept rate: overall "
    "rate with n; sizes are recorded only for accepted suggestions in "
    "event schema v3, so size-quartile accept rates are not computable - "
    "the accepted-size quartile distribution is reported instead and the "
    "schema gap is stated. (3) Scroll coverage: per AI-origin `edit_burst`, "
    "summed visible-range dwell on the same file in the 60 s after the "
    "burst (viewport spans reconstructed from consecutive `visible_range` "
    "events). (4) Latency vs. fatigue: Spearman rank correlation between "
    "each reviewed suggestion's latency and the most recent prior "
    "`fatigue_response` score in the same session. Per-cell n everywhere; "
    "pilot-scale results are hypothesis-generating."
)

#: Window after an AI insertion in which viewing counts as "reviewing it".
REVIEW_WINDOW_S = 60
#: A visible_range span with no successor is assumed visible this long.
LAST_SPAN_S = 5


def _viewport_spans(dataset: Dataset) -> pd.DataFrame:
    """Reconstruct per-file visibility spans from visible_range events."""
    vr = dataset.of_type("visible_range")
    if vr.empty:
        return pd.DataFrame(columns=["sessionId", "file", "start", "end"])
    vr = vr.sort_values(["sessionId", "seq"])
    spans = []
    for sid, g in vr.groupby("sessionId"):
        rows = g.to_dict("records")
        for cur, nxt in zip(rows, [*rows[1:], None], strict=False):
            end = (
                nxt["ts"]
                if nxt is not None
                else cur["ts"] + pd.Timedelta(seconds=LAST_SPAN_S)
            )
            spans.append(
                {
                    "sessionId": sid,
                    "file": cur.get("file"),
                    "start": cur["ts"],
                    "end": end,
                }
            )
    return pd.DataFrame(spans)


@recipe(
    id="ai-review-behavior",
    answers=["RQ-P4"],
    requires_events=["ai_suggestion"],
    title="AI suggestion review: latency, coverage, accept rate",
)
def run(dataset: Dataset) -> RecipeResult:
    sug = dataset.of_type("ai_suggestion")
    terminal = sug[sug["action"].isin(["accepted", "dismissed", "rejected"])].copy()
    terminal["latencyS"] = (
        pd.to_numeric(terminal.get("visibleMs"), errors="coerce") / 1000
    )
    terminal["accepted"] = terminal["action"] == "accepted"
    shown_n = int((sug["action"] == "shown").sum())

    tables: dict[str, pd.DataFrame] = {"suggestions": terminal}
    figs = {}
    sentences = []

    # 1. Review latency: accept vs not-accept.
    acc = terminal.loc[terminal["accepted"], "latencyS"].dropna().tolist()
    rej = terminal.loc[~terminal["accepted"], "latencyS"].dropna().tolist()
    if acc and rej:
        t = stats.mann_whitney(acc, rej, labels=("accepted", "not-accepted"))
        tables["latency_test"] = pd.DataFrame([t.row()])
        sentences.append(f"Review latency: {t.line()}")
    else:
        sentences.append(
            f"Review latency: accepted n={len(acc)}, not-accepted n={len(rej)} "
            "- both outcome groups needed for a comparison; descriptives only."
        )
    # Outcome plays the "condition" role for the house strip plot; the real
    # condition column must go first or the frame ends up with two of them.
    lat_df = terminal.drop(columns=["condition"]).rename(
        columns={"action": "condition"}
    )
    outcomes_present = [
        c
        for c in ["accepted", "dismissed", "rejected"]
        if (lat_df["condition"] == c).any()
    ]
    figs["latency_by_outcome"] = figures.strip_by_condition(
        lat_df,
        "latencyS",
        outcomes_present,
        "Review latency by suggestion outcome",
        "review latency (s)",
        unit_label="suggestion",
        xlabel="suggestion outcome",
    )

    # 2. Accept rate + size quartiles (honest schema-v3 variant).
    accept_rate = terminal["accepted"].mean() if len(terminal) else float("nan")
    sentences.append(
        f"Accept rate: {accept_rate:.0%} of {len(terminal)} reviewed "
        f"suggestions ({shown_n} shown). Sizes are recorded on accepted "
        "suggestions only (schema v3), so accept-rate-by-size-quartile is "
        "not computable - schema gap reported, accepted-size quartiles "
        "given instead."
    )
    sizes = (
        pd.to_numeric(
            terminal.loc[terminal["accepted"], "charCount"], errors="coerce"
        ).dropna()
        if "charCount" in terminal.columns
        else pd.Series(dtype="float64")
    )
    if len(sizes) >= 4:
        quartiles = pd.qcut(sizes, 4, duplicates="drop")
        tables["accepted_size_quartiles"] = (
            sizes.groupby(quartiles, observed=True)
            .agg(n="count", median_chars="median")
            .reset_index(names="size_quartile")
        )
    elif len(sizes):
        tables["accepted_sizes"] = sizes.describe().to_frame().T

    # 3. Scroll coverage of AI-origin bursts (needs the behavioral leg).
    bursts = dataset.of_type("edit_burst")
    spans = _viewport_spans(dataset)
    if not bursts.empty and not spans.empty and "origin" in bursts.columns:
        ai_bursts = bursts[bursts["origin"] == "ai"].copy()
        dwell = []
        for _, b in ai_bursts.iterrows():
            w0, w1 = b["ts"], b["ts"] + pd.Timedelta(seconds=REVIEW_WINDOW_S)
            same = spans[
                (spans["sessionId"] == b["sessionId"])
                & (spans["file"] == b.get("file"))
            ]
            overlap = (
                (same["end"].clip(upper=w1) - same["start"].clip(lower=w0))
                .dt.total_seconds()
                .clip(lower=0)
                .sum()
            )
            dwell.append(
                {
                    "sessionId": b["sessionId"],
                    "condition": b["condition"],
                    "file": b.get("file"),
                    "charsAdded": b.get("charsAdded"),
                    "dwellS": overlap,
                }
            )
        cov = pd.DataFrame(dwell)
        if len(cov):
            tables["ai_burst_scroll_coverage"] = cov
            unviewed = int((cov["dwellS"] < 1).sum())
            sentences.append(
                f"Scroll coverage: {len(cov)} AI-origin burst(s); median "
                f"post-insertion dwell {cov['dwellS'].median():.0f}s in a "
                f"{REVIEW_WINDOW_S}s window; {unviewed} burst(s) with <1s "
                "dwell (inserted without being looked at)."
            )
    else:
        sentences.append(
            "Scroll coverage: skipped - needs `edit_burst` (with origin) and "
            "`visible_range` events alongside `ai_suggestion`."
        )

    # 4. Review latency vs most recent fatigue response.
    fatigue = dataset.of_type("fatigue_response")
    if not fatigue.empty:
        joined = []
        for _, s in terminal.dropna(subset=["latencyS"]).iterrows():
            prior = fatigue[
                (fatigue["sessionId"] == s["sessionId"]) & (fatigue["ts"] <= s["ts"])
            ]
            if len(prior):
                joined.append(
                    {
                        "latencyS": s["latencyS"],
                        "fatigue": prior.sort_values("ts").iloc[-1]["score"],
                    }
                )
        if len(joined) >= 3:
            j = pd.DataFrame(joined)
            t = stats.spearman(
                j["latencyS"].tolist(), j["fatigue"].tolist(), "suggestions"
            )
            tables["latency_vs_fatigue"] = j
            tables["latency_vs_fatigue_test"] = pd.DataFrame([t.row()])
            sentences.append(f"Latency vs latest fatigue: {t.line()}")
            fig, ax = new_axes(
                "Review latency vs. most recent fatigue response",
                "latest fatigue score before the suggestion (1-5)",
                "review latency (s)",
            )
            ax.scatter(
                j["fatigue"],
                j["latencyS"],
                s=30,
                color=figures.PALETTE[0],
                edgecolors=figures.SURFACE,
                linewidths=1.2,
                zorder=3,
            )
            ax.set_xlim(0, 5.4)
            figs["latency_vs_fatigue"] = fig
        else:
            sentences.append(
                f"Latency vs fatigue: only {len(joined)} joinable "
                "suggestion(s) - need >= 3 for a rank correlation."
            )
    else:
        sentences.append("Latency vs fatigue: skipped - no fatigue_response events.")

    return RecipeResult(
        tables=tables,
        figures=figs,
        summary="AI review behavior (RQ-P4). " + " ".join(sentences),
        methods=METHODS,
    )
