"""Rule-based signals, not ground truth about AI use outside the capture boundary."""

from collections import Counter, defaultdict

import pandas as pd
from scipy import stats

from analysis.core import RecipeResult, recipe
from analysis.dataset import Dataset

BLIND_SPOTS = [
    "External CLI agents may arrive as bulk file reloads without AI events.",
    "Drag-and-drop, external clipboard tools and activity "
    "outside the editor may not be captured.",
    "Inline-completion provider queries do not establish that a suggestion "
    "was returned, displayed or accepted.",
    "Inline-suggestion keybindings miss partial accepts, toolbar clicks and "
    "typing-through dismissals.",
    "Bulk-edit heuristics can be triggered by formatters, snippets, renames "
    "and other non-AI edits; they are not counted as AI-use evidence.",
    "Paste alone is ambiguous and does not establish AI origin.",
    "No evidence of AI use is never proof of no AI use.",
]


def audit_sessions(
    rows: list[dict],
    control_conditions: list[str],
    decisions: dict | None = None,
    *,
    include_synthetic: bool = False,
) -> dict:
    """Synthetic rows are audited only on request, for a labelled example view."""
    sessions = defaultdict(list)
    for row in rows:
        if row.get("condition") in control_conditions and (
            include_synthetic or not (row.get("payload") or {}).get("synthetic")
        ):
            sessions[row["sessionId"]].append(row)
    results = []
    for sid, events in sorted(sessions.items()):
        counts = Counter()
        reasons = []
        for row in events:
            payload = row.get("payload") or {}
            kind = row.get("type")
            if kind == "ai_suggestion":
                action = payload.get("action")
                if action == "accepted":
                    counts["accepted_inline_suggestion"] += 1
                elif action in {"shown", "queried"}:
                    # Older TERN versions called a provider query "shown".
                    # The passive provider cannot establish that a suggestion
                    # was actually returned or displayed.
                    counts["inline_completion_query"] += 1
                elif action == "dismissed":
                    counts["dismissed_inline_suggestion"] += 1
            if kind == "edit_burst" and payload.get("origin") == "ai":
                counts["possible_bulk_edit"] += 1
            if kind == "edit_burst" and payload.get("origin") == "paste":
                counts["paste_edit"] += 1
            if kind in {"agent_turn", "tool_call"}:
                counts[kind] += 1
            if kind == "clipboard_paste":
                counts["clipboard_paste"] += 1
        evidence = any(
            counts[k]
            for k in ("accepted_inline_suggestion", "agent_turn", "tool_call")
        )
        if counts["accepted_inline_suggestion"]:
            reasons.append(
                f"Captured {counts['accepted_inline_suggestion']} accepted "
                "inline suggestion(s). This confirms captured inline-completion "
                "use, not total AI use."
            )
        for k in ("agent_turn", "tool_call"):
            if counts[k]:
                reasons.append(f"Captured {counts[k]} {k} event(s).")
        if counts["inline_completion_query"]:
            reasons.append(
                f"TERN recorded {counts['inline_completion_query']} legacy "
                "inline-provider query proxy event(s). VS Code can make these "
                "queries during ordinary typing; they do not show that a "
                "suggestion was returned, displayed or accepted."
            )
        if counts["possible_bulk_edit"]:
            reasons.append(
                f"{counts['possible_bulk_edit']} bulk-edit heuristic signal(s) "
                "were observed; formatters, snippets, renames and other "
                "non-AI edits can trigger this heuristic."
            )
        if counts["clipboard_paste"] or counts["paste_edit"]:
            reasons.append(
                "Paste signals are present; they do not establish AI origin."
            )
        capture_events = [r for r in events if r.get("source", "tern") == "tern"]
        kinds = {r.get("type") for r in capture_events}
        snapshots = [
            r["payload"]
            for r in capture_events
            if r.get("type") == "environment_snapshot"
        ]
        coverage = any(
            all(
                (p.get("auditCapture") or {}).get(k) is True
                for k in ("aiLifecycle", "editBursts", "clipboard")
            )
            for p in snapshots
        )
        seqs = sorted(
            {
                r["seq"]
                for r in events
                if r.get("source", "tern") == "tern" and isinstance(r.get("seq"), int)
            }
        )
        complete = (
            coverage
            and {"session_start", "session_end"} <= kinds
            and bool(seqs)
            and seqs[-1] - seqs[0] + 1 == len(seqs)
        )
        if not complete:
            reasons.append(
                "Capture coverage or complete session boundaries/sequence are missing."
            )
        status = (
            "evidence-of-ai-use"
            if evidence
            else "no-evidence"
            if complete
            else "cannot-assess"
        )
        results.append(
            {
                "sessionId": sid,
                "participantId": events[0].get("participantId"),
                "condition": events[0].get("condition"),
                "status": status,
                "counts": dict(counts),
                "reasons": reasons
                or ["No captured AI signals; external use remains possible."],
                "captureComplete": complete,
                "decision": (decisions or {}).get(sid),
            }
        )
    return {
        "sessions": results,
        "blindSpots": BLIND_SPOTS,
        "accuracy": "Not measured. Independent scripted calibration "
        "sessions are required.",
    }


_CALIBRATION_SIGNALS = (
    "combined",
    "accepted_inline_suggestion",
    "possible_bulk_edit",
    "agent_turn",
    "tool_call",
    "clipboard_paste",
    "paste_edit",
)


def _rate(successes: int, total: int) -> dict:
    if not total:
        return {"value": None, "ci": None, "n": 0}
    ci = stats.binomtest(successes, total).proportion_ci(method="exact")
    return {"value": successes / total, "ci": [ci.low, ci.high], "n": total}


def _calibration_signals(
    assessed: list[dict], labels: dict[str, bool], *, fired: bool = False
) -> dict:
    """Rates over assessed sessions only. `fired` ignores the label.

    "combined" grades every assessed session, because positive evidence stands
    even when capture was incomplete. Every other signal grades only sessions
    with complete capture: an incomplete session may have missed that channel,
    so its silence there is not a negative.
    """
    complete = [s for s in assessed if s["captureComplete"]]
    signals = {}
    for signal in _CALIBRATION_SIGNALS:
        graded = assessed if signal == "combined" else complete
        tp = tn = positives = negatives = fires = 0
        for session in graded:
            truth = labels[session["sessionId"]]
            predicted = (
                session["status"] == "evidence-of-ai-use"
                if signal == "combined"
                else bool(session["counts"].get(signal))
            )
            positives += int(truth)
            negatives += int(not truth)
            tp += int(truth and predicted)
            tn += int(not truth and not predicted)
            fires += int(predicted)
        signals[signal] = {
            "sensitivity": _rate(tp, positives),
            "specificity": _rate(tn, negatives),
        }
        if fired:
            signals[signal]["fired"] = _rate(fires, len(graded))
    return signals


def _incomplete(sessions: list[dict]) -> int:
    return sum(1 for s in sessions if not s["captureComplete"])


def calibration_report(
    audit: dict, labels: dict[str, bool], scenarios: dict[str, str] | None = None
) -> dict:
    """Independent labels only. Abstentions are reported, never counted as negatives.

    With `scenarios`, the same rates are also reported per scripted scenario.
    A scenario with no assessed sessions reports null rates, not zero.
    `incompleteCaptureExcluded` counts labelled sessions with incomplete capture
    (abstentions included), which are left out of every per-signal rate.
    """
    samples = [s for s in audit["sessions"] if s["sessionId"] in labels]
    assessed = [s for s in samples if s["status"] != "cannot-assess"]
    report = {
        "labelled": len(samples),
        "assessed": len(assessed),
        "abstained": len(samples) - len(assessed),
        "incompleteCaptureExcluded": _incomplete(samples),
        "signals": _calibration_signals(assessed, labels),
    }
    if scenarios is not None:
        report["byScenario"] = {}
        for scenario in sorted(set(scenarios.values())):
            group = [s for s in samples if scenarios.get(s["sessionId"]) == scenario]
            if not group:
                continue
            graded = [s for s in group if s["status"] != "cannot-assess"]
            report["byScenario"][scenario] = {
                "labelled": len(group),
                "assessed": len(graded),
                "abstained": len(group) - len(graded),
                "incompleteCaptureExcluded": _incomplete(group),
                "signals": _calibration_signals(graded, labels, fired=True),
            }
    return report


@recipe(id="control_arm_audit", answers=["RQ-P1"], title="Control-arm AI-use audit")
def run(dataset: Dataset) -> RecipeResult:
    controls = dataset.meta.get("control_conditions", [])
    result = audit_sessions(dataset.rows, controls, dataset.meta.get("audit_decisions"))
    return RecipeResult(
        tables={"sessions": pd.DataFrame(result["sessions"])},
        summary=f"Audited {len(result['sessions'])} control sessions. "
        + result["accuracy"],
        methods="Rule-based counts. " + " ".join(BLIND_SPOTS),
    )
