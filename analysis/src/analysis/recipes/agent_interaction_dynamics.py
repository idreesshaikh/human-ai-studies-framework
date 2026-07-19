"""agent-interaction-dynamics (RQ-P5): how the conversation with the agent
unfolds over a session (needs the agent leg).

Test/measure choices: turn cadence is summarized as inter-turn gaps
(skewed durations -> medians + exact Mann-Whitney/Wilcoxon machinery when
two conditions exist); tool-call mix is a plain frequency table (no test -
composition, not hypothesis); reliance loops are counted and their spans
summed per session; conversation-vs-coding time share divides summed
turn-to-turn engagement against the session span (the denominator caveat
is stated); co-variation with the cognitive leg uses Spearman rank
correlations per session pair (fatigue mean, stuck count vs. turns/hour).
"""

from __future__ import annotations

import pandas as pd

from analysis import figures, stats
from analysis.core import RecipeResult, recipe
from analysis.dataset import Dataset
from analysis.recipes._common import compare_or_describe

METHODS = (
    "Agent turns (`agent_turn`) are ordered per session; cadence is the "
    "gap in seconds between consecutive turns, and prompt/response sizes "
    "come from the turn payloads (character counts only under a "
    "metadata-only content policy). Tool-call mix is the frequency of "
    "`tool_call.tool` values. Reliance loops (`reliance_loop`) are counted "
    "per session with their summed duration. Conversation share divides "
    "summed inter-turn engagement (gaps <= 120 s between consecutive agent "
    "events) by the session event span - an approximation stated as such. "
    "Cross-leg co-variation: Spearman rank correlation of per-session "
    "turns/hour against mean fatigue and stuck-episode count. Exact "
    "nonparametric comparisons via analysis.stats when two conditions "
    "exist; per-cell n everywhere; pilot n is hypothesis-generating."
)

ENGAGED_GAP_S = 120


@recipe(
    id="agent-interaction-dynamics",
    answers=["RQ-P5"],
    requires_events=["agent_turn"],
    title="Agent conversation dynamics",
)
def run(dataset: Dataset) -> RecipeResult:
    turns = dataset.of_type("agent_turn").sort_values(["sessionId", "seq"])
    spans = dataset.session_spans
    if "responseChars" not in turns.columns:
        turns["responseChars"] = float("nan")
    turns["responseChars"] = pd.to_numeric(turns["responseChars"], errors="coerce")

    # Cadence: inter-turn gaps.
    turns["gapS"] = turns.groupby("sessionId")["ts"].diff().dt.total_seconds()

    per_session = (
        turns.groupby(["sessionId", "participantId", "condition"], as_index=False)
        .agg(
            turns=("type", "count"),
            medianGapS=("gapS", "median"),
            responseCharsMedian=("responseChars", "median"),
        )
        .merge(spans[["sessionId", "durationMinutes"]], on="sessionId")
    )
    per_session["turnsPerHour"] = per_session["turns"] / (
        per_session["durationMinutes"] / 60
    ).clip(lower=1e-9)

    # Engagement share: agent-adjacent time / session span.
    engaged = (
        turns.assign(engaged=turns["gapS"].clip(upper=ENGAGED_GAP_S))
        .groupby("sessionId")["engaged"]
        .sum()
        .rename("engagedS")
    )
    per_session = per_session.join(engaged, on="sessionId")
    per_session["conversationShare"] = (
        per_session["engagedS"] / (per_session["durationMinutes"] * 60)
    ).clip(0, 1)

    cadence_test, cadence_cells, cadence_sentence = compare_or_describe(
        per_session, "turnsPerHour", dataset
    )

    tables: dict[str, pd.DataFrame] = {
        "per_session": per_session,
        "cadence_per_condition": cadence_cells,
    }
    sentences = [f"Turn cadence: {cadence_sentence}"]
    if cadence_test:
        tables["cadence_test"] = pd.DataFrame([cadence_test.row()])

    # Tool-call mix.
    tools = dataset.of_type("tool_call")
    if not tools.empty and "tool" in tools.columns:
        mix = (
            tools.groupby(["condition", "tool"])
            .size()
            .rename("calls")
            .reset_index()
            .sort_values("calls", ascending=False)
        )
        tables["tool_mix"] = mix
        top = mix.iloc[0]
        sentences.append(
            f"Tool mix: {len(mix)} distinct tools, most used "
            f"{top['tool']!r} ({top['calls']} calls)."
        )

    # Reliance loops.
    loops = dataset.of_type("reliance_loop", "reliance_loop_end")
    if not loops.empty:
        loop_stats = loops.groupby(["sessionId", "condition"], as_index=False).agg(
            loops=("type", "count")
        )
        tables["reliance_loops"] = loop_stats
        sentences.append(
            f"Reliance loops: {int(loop_stats['loops'].sum())} across "
            f"{len(loop_stats)} session(s)."
        )
    else:
        sentences.append("Reliance loops: none detected in this dataset.")

    # Co-variation with the cognitive leg.
    fatigue = dataset.of_type("fatigue_response")
    if not fatigue.empty and len(per_session) >= 3:
        f_mean = fatigue.groupby("sessionId")["score"].mean().rename("fatigueMean")
        j = per_session.join(f_mean, on="sessionId").dropna(subset=["fatigueMean"])
        if len(j) >= 3:
            t = stats.spearman(
                j["turnsPerHour"].tolist(), j["fatigueMean"].tolist(), "sessions"
            )
            tables["turns_vs_fatigue_test"] = pd.DataFrame([t.row()])
            sentences.append(f"Turns/hour vs mean fatigue: {t.line()}")
    else:
        sentences.append(
            "Co-variation with fatigue: needs >= 3 sessions with both agent "
            "turns and fatigue responses."
        )

    # Figures: response sizes, cadence.
    figs = {}
    if turns["responseChars"].notna().any():
        figs["response_sizes"] = figures.strip_by_condition(
            turns,
            "responseChars",
            dataset.conditions,
            "Agent response sizes",
            "response size (chars)",
            unit_label="turn",
        )
    figs["cadence"] = figures.strip_by_condition(
        per_session,
        "turnsPerHour",
        dataset.conditions,
        "Agent turn cadence by condition",
        "turns / hour",
        unit_label="session",
    )

    return RecipeResult(
        tables=tables,
        figures=figs,
        summary="Agent interaction dynamics (RQ-P5). " + " ".join(sentences),
        methods=METHODS,
    )
