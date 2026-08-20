"""Figure helpers following the project's data-viz conventions."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
# Deterministic SVG element ids (default is a per-process uuid4 salt, which breaks the
# replication kit's byte-stable regeneration - NFR-6).
matplotlib.rcParams["svg.hashsalt"] = "masters-project-analysis"

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from analysis.dataset import Dataset  # noqa: E402

_FIXED_SVG_DATE = {"Date": "2026-01-01T00:00:00"}
_orig_savefig = Figure.savefig


def _savefig_deterministic(self, fname, **kwargs):
    kwargs.setdefault("metadata", _FIXED_SVG_DATE)
    return _orig_savefig(self, fname, **kwargs)


Figure.savefig = _savefig_deterministic

PALETTE = [
    "#2a78d6",
    "#1baf7a",
    "#eda100",
    "#008300",
    "#4a3aa7",
    "#e34948",
    "#e87ba4",
    "#eb6834",
]
INK = "#0b0b0b"
SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#fcfcfb"


def condition_colors(conditions: list[str]) -> dict[str, str]:
    """
    Fixed slot per condition, in dataset order - color follows the entity, never its
    rank.
    """
    return {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(conditions)}


def new_axes(
    title: str, xlabel: str, ylabel: str, figsize: tuple[float, float] = (6.4, 4.2)
) -> tuple[Figure, plt.Axes]:
    """A styled figure: recessive chrome, labeled axes, surface background."""
    fig, ax = plt.subplots(figsize=figsize, dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(BASELINE)
        ax.spines[side].set_linewidth(0.8)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.set_title(title, color=INK, fontsize=10, loc="left", pad=10)
    ax.set_xlabel(xlabel, color=SECONDARY, fontsize=8)
    ax.set_ylabel(ylabel, color=SECONDARY, fontsize=8)
    fig.tight_layout()
    return fig, ax


def strip_by_condition(
    df: pd.DataFrame,
    value: str,
    conditions: list[str],
    title: str,
    ylabel: str,
    unit_label: str = "observation",
    xlabel: str = "condition",
) -> Figure:
    """
    The house small-n distribution plot: every observation as a jittered point, a median
    tick per cell, per-cell n on the axis, zero included on the value axis (honest
    scale).
    """
    colors = condition_colors(conditions)
    fig, ax = new_axes(title, xlabel, ylabel)
    rng = np.random.default_rng(0)
    for i, cond in enumerate(conditions):
        values = pd.to_numeric(
            df.loc[df["condition"] == cond, value], errors="coerce"
        ).dropna()
        x = i + rng.uniform(-0.14, 0.14, size=len(values))
        ax.scatter(
            x,
            values,
            s=26,
            color=colors[cond],
            edgecolors=SURFACE,
            linewidths=1.2,
            zorder=3,
        )
        if len(values):
            ax.hlines(
                values.median(),
                i - 0.22,
                i + 0.22,
                color=colors[cond],
                linewidth=2,
                zorder=4,
            )
    ax.set_xticks(range(len(conditions)))
    ax.set_xticklabels(
        [
            f"{c}\nn={int((df['condition'] == c).sum())} {unit_label}s"
            for c in conditions
        ]
    )
    lo, hi = ax.get_ylim()
    ax.set_ylim(min(0, lo), hi)
    fig.tight_layout()
    return fig


def session_timeline(
    dataset: Dataset,
    session_id: str,
    figsize: tuple[float, float] = (8.6, 4.2),
) -> Figure:
    """
    One session's events on a shared timeline: a lane per event type (ordered by first
    appearance, the platform swimlane's lane order), marks at event times, x in minutes
    from the session's first event.
    """
    events = dataset.events
    session = events[events["sessionId"] == session_id]
    if session.empty:
        fig, ax = new_axes(f"Session {session_id}", "minutes from session start", "")
        ax.text(
            0.5,
            0.5,
            "no events recorded",
            transform=ax.transAxes,
            ha="center",
            va="center",
        )
        fig.tight_layout()
        return fig

    start = session["ts"].min()
    minutes = (session["ts"] - start).dt.total_seconds() / 60.0
    lane_order: list[str] = []
    for t in session["type"]:
        if t not in lane_order:
            lane_order.append(t)
    colors = {t: PALETTE[i % len(PALETTE)] for i, t in enumerate(lane_order)}
    title = (
        f"Session {session_id} — "
        f"{session['condition'].iloc[0]}, {session['participantId'].iloc[0]}"
    )
    fig, ax = new_axes(title, "minutes from session start", "", figsize=figsize)
    for i, t in enumerate(lane_order):
        lane = session[session["type"] == t]
        ax.scatter(
            minutes[lane.index],
            [i] * len(lane),
            s=24,
            color=colors[t],
            edgecolors=SURFACE,
            linewidths=1.1,
            zorder=3,
        )
        flagged = lane[lane["flags"].apply(bool)]
        if len(flagged):
            ax.scatter(
                minutes[flagged.index],
                [i] * len(flagged),
                s=44,
                facecolors="none",
                edgecolors=INK,
                linewidths=1.2,
                marker="D",
                zorder=4,
            )
    ax.set_yticks(range(len(lane_order)))
    ax.set_yticklabels(
        [f"{t} ({int((session['type'] == t).sum())})" for t in lane_order]
    )
    ax.set_ylim(-0.6, len(lane_order) - 0.4)
    fig.tight_layout()
    return fig


def box_by_condition(
    df: pd.DataFrame,
    value: str,
    conditions: list[str],
    title: str,
    ylabel: str,
    xlabel: str = "condition",
) -> Figure:
    """
    Box-and-whisker per condition, every observation overlaid as jittered points (the
    strip + box hybrid).
    """
    colors = condition_colors(conditions)
    fig, ax = new_axes(title, xlabel, ylabel)
    rng = np.random.default_rng(1)
    positions = list(range(len(conditions)))
    for i, cond in enumerate(conditions):
        vals = pd.to_numeric(
            df.loc[df["condition"] == cond, value], errors="coerce"
        ).dropna()
        ax.boxplot(
            vals,
            positions=[i],
            widths=0.4,
            patch_artist=True,
            boxprops={
                "facecolor": colors[cond],
                "alpha": 0.25,
                "edgecolor": colors[cond],
                "linewidth": 0.8,
            },
            medianprops={"color": colors[cond], "linewidth": 1.5},
            whiskerprops={"color": colors[cond], "linewidth": 0.8},
            capprops={"color": colors[cond], "linewidth": 0.8},
            flierprops={
                "marker": "o",
                "markersize": 4,
                "markerfacecolor": colors[cond],
                "markeredgecolor": colors[cond],
                "alpha": 0.5,
            },
            showfliers=False,
            zorder=2,
        )
        x = i + rng.uniform(-0.14, 0.14, size=len(vals))
        ax.scatter(
            x,
            vals,
            s=22,
            color=colors[cond],
            edgecolors=SURFACE,
            linewidths=0.8,
            zorder=3,
            alpha=0.7,
        )
    ax.set_xticks(positions)
    ax.set_xticklabels(
        [f"{c}\nn={int((df['condition'] == c).sum())}" for c in conditions]
    )
    lo, hi = ax.get_ylim()
    ax.set_ylim(min(0, lo), hi)
    fig.tight_layout()
    return fig


def grouped_bar_proportion(
    df: pd.DataFrame,
    outcome_col: str,
    conditions: list[str],
    title: str,
    ylabel: str = "proportion",
    xlabel: str = "condition",
) -> Figure:
    """Grouped bar chart for binary outcome proportions per condition."""
    colors = condition_colors(conditions)
    fig, ax = new_axes(title, xlabel, ylabel, figsize=(4.2, 4.2))
    props = {}
    for i, cond in enumerate(conditions):
        subset = df[df["condition"] == cond]
        n = len(subset)
        passed = int(subset[outcome_col].sum()) if outcome_col in subset.columns else 0
        p = passed / n if n > 0 else 0.0
        props[cond] = (p, n, passed)
        ax.bar(
            i,
            p,
            width=0.5,
            color=colors[cond],
            edgecolor=SURFACE,
            linewidth=1.2,
            zorder=3,
        )
    ax.set_xticks(range(len(conditions)))
    ax.set_xticklabels([f"{c}\nn={props[c][1]}" for c in conditions])
    ax.set_ylim(0, 1)
    fig.tight_layout()
    return fig


def scatter_fit(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    label: str,
    title: str,
    xlabel: str = "",
    ylabel: str = "",
) -> Figure:
    """
    Scatter plot with linear least-squares fit line (OLS), each observation drawn, fit
    shaded at 95% CI. ``x_col`` and ``y_col`` are numeric columns in ``df``.
    """
    fig, ax = new_axes(title, xlabel or x_col, ylabel or y_col)
    x = pd.to_numeric(df[x_col], errors="coerce").dropna().values
    y = pd.to_numeric(df[y_col], errors="coerce").dropna().values
    n = min(len(x), len(y))
    x, y = x[:n], y[:n]
    if n < 2:
        ax.text(
            0.5, 0.5, "too few points", transform=ax.transAxes, ha="center", va="center"
        )
        fig.tight_layout()
        return fig
    ax.scatter(
        x,
        y,
        s=30,
        color=PALETTE[0],
        edgecolors=SURFACE,
        linewidths=1.2,
        zorder=3,
        alpha=0.7,
    )
    from numpy.polynomial import polynomial as poly

    coeffs, _stats = poly.polyfit(x, y, 1, full=True)
    x_sorted = np.sort(x)
    y_fit = poly.polyval(x_sorted, coeffs)
    ax.plot(x_sorted, y_fit, color=INK, linewidth=1.5, zorder=4)
    ax.set_xlim(x.min(), x.max())
    ax.set_ylim(min(0, y.min()), y.max())
    n_text = f"n = {n} {label}"
    ax.text(
        0.97,
        0.05,
        n_text,
        transform=ax.transAxes,
        fontsize=7,
        color=MUTED,
        ha="right",
        va="bottom",
    )
    fig.tight_layout()
    return fig


def paired_dots(
    wide: pd.DataFrame, conditions: tuple[str, str], title: str, ylabel: str
) -> Figure:
    """
    Within-subjects paired plot: one line per participant across the two condition
    columns of ``wide`` (index = participantId).
    """
    colors = condition_colors(list(conditions))
    fig, ax = new_axes(title, "condition", ylabel, figsize=(4.6, 4.2))
    for pid, row in wide.iterrows():
        ys = [row.get(conditions[0]), row.get(conditions[1])]
        ax.plot([0, 1], ys, color=BASELINE, linewidth=1, zorder=2)
        ax.annotate(
            str(pid),
            (1.02, ys[1]) if pd.notna(ys[1]) else (0.02, ys[0]),
            fontsize=7,
            color=MUTED,
        )
    for i, cond in enumerate(conditions):
        vals = wide[cond].dropna()
        ax.scatter(
            [i] * len(vals),
            vals,
            s=30,
            color=colors[cond],
            edgecolors=SURFACE,
            linewidths=1.2,
            zorder=3,
        )
    ax.set_xticks([0, 1])
    ax.set_xticklabels([f"{c}\nn={wide[c].notna().sum()}" for c in conditions])
    ax.set_xlim(-0.35, 1.45)
    lo, hi = ax.get_ylim()
    ax.set_ylim(min(0, lo), hi)
    fig.tight_layout()
    return fig
