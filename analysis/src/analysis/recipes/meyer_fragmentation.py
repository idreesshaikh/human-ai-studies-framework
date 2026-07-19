"""meyer-fragmentation (RQ-P3): work fragmentation as a recipe - the
second published-paper replication (FR-ANA-5).

Replicates the fragmentation analysis of:

    Meyer, Barton, Murphy, Zimmermann, Fritz. "The Work Life of
    Developers: Activities, Switches and Perceived Productivity."
    IEEE Transactions on Software Engineering 43(12):1178-1193, 2017.
    DOI 10.1109/TSE.2017.2656886.

Meyer et al. instrumented 20 professional developers' machines and found
highly fragmented work - frequent short activities and context switches -
and that developers perceive days with *fewer* switches as more
productive. Session-scale mapping: their activity switch becomes the
**editor file switch** (`editor_focus` events carrying a `file` payload,
debounced by the instrument; consecutive events on the same file collapse,
so a switch is a *change* of file); their fragmentation measures become
switches per hour and focus-segment durations; their experience-sampled
perceived productivity becomes our fatigue probes - the closest
self-report on this timeline, an explicit stand-in stated in methods, as
in `ziegler-acceptance-rate`.

Test choices: switch rates and segment durations are skewed, tiny-n
quantities -> the exact Wilcoxon/Mann-Whitney machinery of
``analysis.stats`` (per-participant means against pseudo-replication);
switch-rate x fatigue co-variation via Spearman rank correlation.
"""

from __future__ import annotations

import pandas as pd

from analysis import figures, stats
from analysis.core import RecipeResult, recipe
from analysis.dataset import Dataset
from analysis.recipes._common import compare_or_describe

METHODS = (
    "Replication of Meyer et al. (IEEE TSE 43(12), 2017, DOI "
    "10.1109/TSE.2017.2656886) at session scale. A switch is a change of "
    "file in consecutive file-bearing `editor_focus` events (instrument- "
    "debounced; same-file repeats collapsed). Fragmentation per session: "
    "switches per hour over the session event span (an upper bound on "
    "active time - the paper's active-window denominators arrive with "
    "idle-corrected denominators) and focus-segment durations (minutes "
    "between consecutive switches). Conditions compared with the exact "
    "Wilcoxon signed-rank on per-participant means (paired) or exact "
    "Mann-Whitney U with Cliff's delta (unpaired). Where the paper "
    "correlates switching with experience-sampled perceived productivity, "
    "the pilot correlates switch rate with the session's mean fatigue "
    "response (Spearman) - an explicit stand-in, reported as such. "
    "Per-cell n everywhere; pilot n is hypothesis-generating."
)


@recipe(
    id="meyer-fragmentation",
    answers=["RQ-P3"],
    requires_events=["editor_focus"],
    title="Work fragmentation per Meyer et al. 2017 (replication demo 2)",
)
def run(dataset: Dataset) -> RecipeResult:
    focus = dataset.of_type("editor_focus")
    spans = dataset.session_spans

    sentences = []
    if "file" not in focus.columns:
        focus = focus.assign(file=pd.NA)
    switches_rows = []
    segment_rows = []
    for sid, g in focus.dropna(subset=["file"]).groupby("sessionId"):
        g = g.sort_values("seq")
        changed = g[g["file"] != g["file"].shift()]
        switches_rows.append(
            {
                "sessionId": sid,
                "participantId": g["participantId"].iloc[0],
                "condition": g["condition"].iloc[0],
                "switches": max(len(changed) - 1, 0),
            }
        )
        seg = changed["ts"].diff().dt.total_seconds().dropna() / 60
        segment_rows += [
            {
                "sessionId": sid,
                "participantId": g["participantId"].iloc[0],
                "condition": g["condition"].iloc[0],
                "segmentMinutes": s,
            }
            for s in seg
        ]

    per_session = spans.merge(
        pd.DataFrame(
            switches_rows,
            columns=[
                "sessionId",
                "participantId",
                "condition",
                "switches",
            ],
        )[["sessionId", "switches"]],
        on="sessionId",
        how="left",
    ).fillna({"switches": 0})
    per_session["switchesPerHour"] = per_session["switches"] / (
        per_session["durationMinutes"] / 60
    ).clip(lower=1e-9)

    rate_test, rate_cells, rate_sentence = compare_or_describe(
        per_session, "switchesPerHour", dataset
    )
    sentences.append(f"Switch rate: {rate_sentence}")

    tables: dict[str, pd.DataFrame] = {
        "per_session": per_session,
        "rate_per_condition": rate_cells,
    }
    if rate_test:
        tables["rate_test"] = pd.DataFrame([rate_test.row()])

    segments = pd.DataFrame(
        segment_rows,
        columns=["sessionId", "participantId", "condition", "segmentMinutes"],
    )
    if len(segments):
        seg_test, seg_cells, seg_sentence = compare_or_describe(
            segments, "segmentMinutes", dataset
        )
        tables["segments"] = segments
        tables["segment_per_condition"] = seg_cells
        if seg_test:
            tables["segment_test"] = pd.DataFrame([seg_test.row()])
        sentences.append(f"Focus segments: {seg_sentence}")
    else:
        sentences.append(
            "Focus segments: no file-bearing editor_focus switches in this "
            "dataset (single-file sessions or capture off) - rates are 0, "
            "segment durations not computable."
        )

    # The paper's productivity link: switching vs self-report (fatigue).
    fatigue = dataset.of_type("fatigue_response")
    if not fatigue.empty:
        f_mean = fatigue.groupby("sessionId")["score"].mean().rename("fatigueMean")
        joined = per_session.join(f_mean, on="sessionId").dropna(subset=["fatigueMean"])
        if len(joined) >= 3:
            t = stats.spearman(
                joined["switchesPerHour"].tolist(),
                joined["fatigueMean"].tolist(),
                "sessions",
            )
            tables["rate_vs_fatigue_test"] = pd.DataFrame([t.row()])
            sentences.append(
                "Switch rate vs mean fatigue (paper's perceived-productivity "
                f"stand-in): {t.line()}"
            )
        else:
            sentences.append(
                "Switch-rate-vs-fatigue correlation needs >= 3 sessions with "
                f"both measures (have {len(joined)})."
            )

    figs = {
        "switch_rate": figures.strip_by_condition(
            per_session,
            "switchesPerHour",
            dataset.conditions,
            "File-switch rate per session (Meyer et al. 2017)",
            "switches / hour",
            unit_label="session",
        )
    }
    if len(segments):
        figs["focus_segments"] = figures.strip_by_condition(
            segments,
            "segmentMinutes",
            dataset.conditions,
            "Focus-segment durations (Meyer et al. 2017)",
            "minutes between file switches",
            unit_label="segment",
        )

    return RecipeResult(
        tables=tables,
        figures=figs,
        summary="Work fragmentation, replication demo 2 (RQ-P3). "
        + " ".join(sentences),
        methods=METHODS,
    )
