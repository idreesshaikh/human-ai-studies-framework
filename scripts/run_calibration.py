"""Turn the labelled calibration sessions into the verification-limit matrix.

    uv run --no-sync python scripts/run_calibration.py \\
        --rows <rows files> --labels labels.csv --out <dir>

--rows takes one or more files of event rows, as StudyLoop stores them: JSONL
(one row per line, as TERN writes it), a dataset export
(`GET /studies/{id}/dataset?format=json`), or a JSON array of rows. Rows from
several files are merged; a row seen twice (same sessionId, source and seq) is
kept once.

--labels is the operator's labels.csv
(`sessionId,scenario,aiUsed,exposed,assisted,rep,operatorNote`).

Writes to --out:
    matrix.csv   scenario,signal,fired,fired_ci_low,fired_ci_high,n,abstained
    report.json  `calibration_report` with per-scenario strata
    matrix.png   heatmap of the fired rate, scenario by signal

Characterisation, not accuracy: with 1-2 sessions per scenario the exact 95%
intervals are wide, and nothing here is tuned on the sessions.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from analysis.recipes.control_arm_audit import audit_sessions, calibration_report
from calibration_order import GROUP_OF, SCENARIOS
from matplotlib.colors import LinearSegmentedColormap, to_rgb
from matplotlib.patches import Rectangle
from scipy.stats import binomtest

# RECAP, He et al. (2026), arXiv:2605.01104, flags implied speed >100 WPM.
# The paper does not state chars/word or a size threshold; these are our choices.
TYPING_CHARS_PER_WORD = 5
TYPING_MIN_CHARS = 20
TYPING_WPM_THRESHOLD = 100

MATRIX_COLUMNS = [
    "scenario",
    "signal",
    "fired",
    "fired_ci_low",
    "fired_ci_high",
    "n",
    "abstained",
]
TRUE_WORDS = {"true", "1", "yes"}
FALSE_WORDS = {"false", "0", "no"}
LABEL_HEADER = [
    "sessionId",
    "scenario",
    "aiUsed",
    "exposed",
    "assisted",
    "rep",
    "operatorNote",
]


class CalibrationError(Exception):
    """A problem with the inputs that the researcher can fix."""


# --- inputs ----------------------------------------------------------------


def _rows_in(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CalibrationError(f"cannot read rows file {path}: {exc}") from exc
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        document = None
    if isinstance(document, dict) and isinstance(document.get("rows"), list):
        rows = document["rows"]
    elif isinstance(document, list):
        rows = document
    elif isinstance(document, dict):
        rows = [document]  # a one-line JSONL file
    else:
        rows = []
        for number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise CalibrationError(
                    f"{path} line {number} is not valid JSON ({exc.msg})"
                ) from exc
    if not all(isinstance(row, dict) for row in rows):
        raise CalibrationError(f"{path} holds rows that are not JSON objects")
    return rows


def load_rows(paths: list[Path]) -> list[dict]:
    """Merge rows from every file; ingest's (sessionId, source, seq) is the key."""
    merged: list[dict] = []
    seen: dict[tuple, dict] = {}
    for path in paths:
        for row in _rows_in(path):
            if "sessionId" not in row:
                raise CalibrationError(f"{path} has a row without a sessionId")
            if isinstance(row.get("seq"), int):
                key = (row["sessionId"], row.get("source") or "tern", row["seq"])
                if key in seen:
                    if seen[key] != row:
                        raise CalibrationError(f"conflicting duplicate row: {key!r}")
                    continue
                seen[key] = row
            merged.append(row)
    return merged


def load_labels(
    path: Path,
) -> tuple[dict[str, bool], dict[str, str], dict[str, dict[str, int]]]:
    """Return validated labels, scenarios and per-scenario label counts."""
    try:
        handle = path.open(newline="", encoding="utf-8")
    except OSError as exc:
        raise CalibrationError(f"cannot read labels file {path}: {exc}") from exc
    labels: dict[str, bool] = {}
    scenarios: dict[str, str] = {}
    summary: dict[str, dict[str, int]] = {}
    with handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != LABEL_HEADER:
            raise CalibrationError(f"{path}: expected header {','.join(LABEL_HEADER)}")
        for number, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise CalibrationError(
                    f"{path} line {number}: expected {len(LABEL_HEADER)} fields"
                )
            if not any((value or "").strip() for value in row.values()):
                continue
            session = (row["sessionId"] or "").strip()
            scenario = (row["scenario"] or "").strip()
            used = (row["aiUsed"] or "").strip().lower()
            if not session:
                raise CalibrationError(f"{path} line {number}: empty sessionId")
            if scenario not in SCENARIOS:
                raise CalibrationError(
                    f"{path} line {number}: unknown scenario {scenario!r}; "
                    f"expected one of {', '.join(SCENARIOS)}"
                )
            if used not in TRUE_WORDS | FALSE_WORDS:
                raise CalibrationError(
                    f"{path} line {number}: aiUsed must be true or false, "
                    f"got {row['aiUsed']!r}"
                )
            for name in ("exposed", "assisted"):
                if row[name] not in {"true", "false"}:
                    raise CalibrationError(
                        f"{path} line {number}: {name} must be true or false, "
                        f"got {row[name]!r}"
                    )
            if session in labels:
                raise CalibrationError(
                    f"{path} line {number}: duplicate sessionId {session!r}"
                )
            labels[session] = used in TRUE_WORDS
            scenarios[session] = scenario
            counts = summary.setdefault(
                scenario, {"labelled": 0, "aiUsed": 0, "exposed": 0, "assisted": 0}
            )
            counts["labelled"] += 1
            counts["aiUsed"] += labels[session]
            counts["exposed"] += row["exposed"] == "true"
            counts["assisted"] += row["assisted"] == "true"
    if not labels:
        raise CalibrationError(
            f"no labelled sessions in {path}; record one row per session first"
        )
    return labels, scenarios, summary


# --- analysis --------------------------------------------------------------


def typing_speed_flag(row: dict) -> bool:
    """Whether a TERN burst exceeds the declared RECAP speed threshold."""
    if row.get("source", "tern") != "tern" or row.get("type") != "edit_burst":
        return False
    payload = row.get("payload") or {}
    chars = payload.get("charsAdded", 0)
    duration = payload.get("durationMs")
    if chars < TYPING_MIN_CHARS or duration is None or duration < 0:
        return False
    return duration == 0 or (
        (chars / TYPING_CHARS_PER_WORD) / (duration / 60000) > TYPING_WPM_THRESHOLD
    )


def _rate(successes: int, total: int) -> dict:
    if not total:
        return {"value": None, "ci": None, "n": 0}
    ci = binomtest(successes, total).proportion_ci(method="exact")
    return {"value": successes / total, "ci": [ci.low, ci.high], "n": total}


def _typing_rates(sessions: list[dict], labels: dict[str, bool], fires: set) -> dict:
    complete = [s["sessionId"] for s in sessions if s["captureComplete"]]
    positive = [sid for sid in complete if labels[sid]]
    negative = [sid for sid in complete if not labels[sid]]
    return {
        "sensitivity": _rate(sum(sid in fires for sid in positive), len(positive)),
        "specificity": _rate(sum(sid not in fires for sid in negative), len(negative)),
        "fired": _rate(sum(sid in fires for sid in complete), len(complete)),
    }


def _labelled_report(audit: dict, labels: dict, scenarios: dict, fires: set) -> dict:
    """Include missing captures as abstentions without changing the audit."""
    captured = {s["sessionId"] for s in audit["sessions"]}
    missing = sorted(set(labels) - captured)
    sessions = audit["sessions"] + [
        {"sessionId": sid, "status": "cannot-assess", "captureComplete": False}
        for sid in missing
    ]
    report = calibration_report({"sessions": sessions}, labels, scenarios)
    labelled = [s for s in sessions if s["sessionId"] in labels]
    report["signals"]["typing_speed_flag"] = _typing_rates(labelled, labels, fires)
    for scenario, stratum in report["byScenario"].items():
        group = [s for s in labelled if scenarios.get(s["sessionId"]) == scenario]
        stratum["signals"]["typing_speed_flag"] = _typing_rates(group, labels, fires)
    report["unmatchedLabels"] = missing
    report["unlabelledSessions"] = sorted(captured - set(labels))
    return report


def build_report(
    rows: list[dict], labels: dict[str, bool], scenarios: dict[str, str]
) -> dict:
    """Audit every condition and report channel health alongside the rates."""
    conditions = sorted({row.get("condition") for row in rows}, key=str)
    audit = audit_sessions(rows, conditions)
    fires = {r["sessionId"] for r in rows if typing_speed_flag(r)}
    report = _labelled_report(audit, labels, scenarios, fires)
    health = {
        sid: {"sensorErrors": 0, "errorSources": []}
        for sid in sorted(set(labels) | {r["sessionId"] for r in rows})
    }
    for row in rows:
        if row.get("type") == "behavior_sensor_error":
            entry = health[row["sessionId"]]
            entry["sensorErrors"] += 1
            source = (row.get("payload") or {}).get("source")
            if source is not None and source not in entry["errorSources"]:
                entry["errorSources"].append(source)
    for entry in health.values():
        entry["errorSources"].sort()
    report["channelHealth"] = health
    healthy_labels = {
        sid: used for sid, used in labels.items() if not health[sid]["sensorErrors"]
    }
    report["excludingSensorErrors"] = _labelled_report(
        audit,
        healthy_labels,
        {sid: scenarios[sid] for sid in healthy_labels},
        fires,
    )
    return report


def matrix_rows(report: dict, scenarios: dict[str, str]) -> list[dict]:
    """One row per scenario and signal. A labelled session with no captured rows
    is an abstention, so it adds to `abstained` and never to a rate."""
    present = set(scenarios.values())
    rows = []
    for scenario in (s for s in SCENARIOS if s in present):
        stratum = report["byScenario"].get(scenario)
        abstained = stratum["abstained"] if stratum else 0
        for signal in report["signals"]:
            rate = stratum["signals"][signal]["fired"] if stratum else None
            ci = (rate or {}).get("ci")
            rows.append(
                {
                    "scenario": scenario,
                    "signal": signal,
                    "fired": _cell((rate or {}).get("value")),
                    "fired_ci_low": _cell(ci[0] if ci else None),
                    "fired_ci_high": _cell(ci[1] if ci else None),
                    "n": (rate or {}).get("n", 0),
                    "abstained": abstained,
                }
            )
    return rows


def _cell(value: float | None) -> str:
    return "" if value is None else str(round(value, 4))


# --- outputs ---------------------------------------------------------------

# Single-hue sequential ramp (steps 100 to 700 of the reference blue): more is
# darker, and it stays ordered under every common colour-vision deficiency.
SEQUENTIAL = LinearSegmentedColormap.from_list(
    "fired_rate", ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
)
INK = "#1a1a19"
MUTED = "#5f5e5a"
NA_FILL = "#e4e3df"


def _luminance(rgb: tuple[float, float, float]) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _ink_on(rgb: tuple[float, float, float]) -> str:
    """Whichever of white and ink has the higher contrast on this fill."""
    lum = _luminance(rgb)
    on_white = 1.05 / (lum + 0.05)
    on_ink = (lum + 0.05) / (_luminance(to_rgb(INK)) + 0.05)
    return "white" if on_white >= on_ink else INK


def _truth(scenario: str, labels: dict[str, bool], scenarios: dict[str, str]) -> str:
    values = {labels[sid] for sid, s in scenarios.items() if s == scenario}
    if values == {True}:
        return "AI used"
    if values == {False}:
        return "no AI"
    return "mixed labels"


def draw_matrix(
    rows: list[dict],
    report: dict,
    labels: dict[str, bool],
    scenarios: dict[str, str],
    path: Path,
) -> None:
    present = [s for s in SCENARIOS if s in set(scenarios.values())]
    signals = list(report["signals"])
    cell = {(r["scenario"], r["signal"]): r for r in rows}

    fig, ax = plt.subplots(
        figsize=(1.15 * len(signals) + 5.2, 0.62 * len(present) + 2.6)
    )
    ax.set_xlim(0, len(signals))
    ax.set_ylim(len(present), 0)
    for y, scenario in enumerate(present):
        for x, signal in enumerate(signals):
            row = cell[(scenario, signal)]
            if row["fired"] == "":
                ax.add_patch(
                    Rectangle(
                        (x, y),
                        1,
                        1,
                        facecolor=NA_FILL,
                        edgecolor="#a9a8a2",
                        hatch="////",
                        linewidth=0,
                    )
                )
                backing = {"facecolor": NA_FILL, "edgecolor": "none", "pad": 1.5}
                ax.text(
                    x + 0.5,
                    y + 0.36,
                    "NA",
                    ha="center",
                    va="center",
                    color=INK,
                    fontweight="bold",
                    bbox=backing,
                )
                ax.text(
                    x + 0.5,
                    y + 0.68,
                    f"n={row['n']}",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color=INK,
                    bbox=backing,
                )
                continue
            value = float(row["fired"])
            fill = SEQUENTIAL(value)
            ax.add_patch(Rectangle((x, y), 1, 1, facecolor=fill, linewidth=0))
            ink = _ink_on(fill[:3])
            ax.text(
                x + 0.5,
                y + 0.36,
                f"{value:.2f}",
                ha="center",
                va="center",
                color=ink,
                fontweight="bold",
            )
            ax.text(
                x + 0.5,
                y + 0.68,
                f"n={row['n']}",
                ha="center",
                va="center",
                fontsize=7,
                color=ink,
            )
    # A 2px surface gap between cells, and a heavier one between scenario groups.
    for x in range(len(signals) + 1):
        ax.axvline(x, color="white", linewidth=2)
    for y in range(len(present) + 1):
        grouped = 0 < y < len(present) and (
            GROUP_OF[present[y - 1]] != GROUP_OF[present[y]]
        )
        ax.axhline(
            y, color="white" if not grouped else INK, linewidth=2 if not grouped else 1
        )

    ax.set_xticks([x + 0.5 for x in range(len(signals))])
    ax.set_xticklabels(signals, rotation=30, ha="left", color=INK, fontsize=8)
    ax.xaxis.tick_top()
    ax.set_yticks([y + 0.5 for y in range(len(present))])
    ax.set_yticklabels(
        [f"{s}  [{_truth(s, labels, scenarios)}]" for s in present],
        color=INK,
        fontsize=8,
    )
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.text(
        len(signals) + 0.15,
        -0.12,
        "abstained",
        ha="left",
        va="bottom",
        fontsize=8,
        color=MUTED,
    )
    for y, scenario in enumerate(present):
        ax.text(
            len(signals) + 0.15,
            y + 0.5,
            str(cell[(scenario, signals[0])]["abstained"]),
            ha="left",
            va="center",
            fontsize=8,
            color=INK,
        )

    colorbar = fig.colorbar(
        plt.cm.ScalarMappable(norm=plt.Normalize(0, 1), cmap=SEQUENTIAL),
        ax=ax,
        fraction=0.025,
        pad=0.1,
    )
    colorbar.set_label(
        "fired rate (fraction of graded sessions)", color=INK, fontsize=8
    )
    colorbar.outline.set_visible(False)
    colorbar.ax.tick_params(labelsize=7, colors=MUTED)

    fig.suptitle(
        "Which TERN signals fire, by scenario: characterisation, not accuracy",
        x=0.02,
        ha="left",
        fontsize=11,
        color=INK,
    )
    fig.text(
        0.02,
        0.015,
        "n = graded sessions (per-signal: complete capture only; "
        "combined: all assessed). "
        "Hatched grey NA = no graded session.\n"
        "Rows show the ground-truth label in brackets: a fire on a [no AI] row is a "
        "false positive, a silence on an [AI used] row a miss. Exact 95% intervals "
        "are in matrix.csv.",
        fontsize=7,
        color=MUTED,
        va="bottom",
    )
    fig.subplots_adjust(left=0.27, right=0.88, top=0.82, bottom=0.11)
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--rows", nargs="+", required=True, type=Path)
    parser.add_argument("--labels", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        labels, scenarios, label_summary = load_labels(args.labels)
        rows = load_rows(args.rows)
    except CalibrationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    report = build_report(rows, labels, scenarios)
    report["labelSummary"] = label_summary
    if report["unmatchedLabels"]:
        print(
            "warning: labelled session(s) with no captured rows, counted as "
            f"abstentions: {', '.join(report['unmatchedLabels'])}",
            file=sys.stderr,
        )
    if report["unlabelledSessions"]:
        print(
            "note: captured session(s) with no label, left out: "
            f"{', '.join(report['unlabelledSessions'])}",
            file=sys.stderr,
        )

    table = matrix_rows(report, scenarios)
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "matrix.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MATRIX_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(table)
    (args.out / "report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    draw_matrix(table, report, labels, scenarios, args.out / "matrix.png")
    print(f"wrote matrix.csv, report.json and matrix.png to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
