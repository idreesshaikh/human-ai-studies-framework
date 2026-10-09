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
    "Edit-origin heuristics have no independent ground truth; "
    "paste alone is ambiguous.",
    "No evidence of AI use is never proof of no AI use.",
]


def audit_sessions(
    rows: list[dict], control_conditions: list[str], decisions: dict | None = None
) -> dict:
    sessions = defaultdict(list)
    for row in rows:
        if row.get("condition") in control_conditions and not (
            row.get("payload") or {}
        ).get("synthetic"):
            sessions[row["sessionId"]].append(row)
    results = []
    for sid, events in sorted(sessions.items()):
        counts = Counter()
        reasons = []
        for row in events:
            payload = row.get("payload") or {}
            kind = row.get("type")
            if kind == "ai_suggestion":
                counts["ai_suggestion"] += 1
            if kind == "edit_burst" and payload.get("origin") == "ai":
                counts["ai_edit_heuristic"] += 1
            if kind == "edit_burst" and payload.get("origin") == "paste":
                counts["paste_edit"] += 1
            if kind in {"agent_turn", "tool_call"}:
                counts[kind] += 1
            if kind == "clipboard_paste":
                counts["clipboard_paste"] += 1
        evidence = any(
            counts[k]
            for k in ("ai_suggestion", "ai_edit_heuristic", "agent_turn", "tool_call")
        )
        if counts["ai_edit_heuristic"]:
            reasons.append(
                "Edit-origin heuristic marked AI; this signal is unvalidated."
            )
        for k in ("ai_suggestion", "agent_turn", "tool_call"):
            if counts[k]:
                reasons.append(f"Captured {counts[k]} {k} event(s).")
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


def calibration_report(audit: dict, labels: dict[str, bool]) -> dict:
    """Independent labels only. Abstentions are reported, never counted as negatives."""
    samples = [s for s in audit["sessions"] if s["sessionId"] in labels]
    assessed = [s for s in samples if s["status"] != "cannot-assess"]
    report = {
        "labelled": len(samples),
        "assessed": len(assessed),
        "abstained": len(samples) - len(assessed),
        "signals": {},
    }
    for signal in (
        "combined",
        "ai_suggestion",
        "ai_edit_heuristic",
        "agent_turn",
        "tool_call",
        "clipboard_paste",
        "paste_edit",
    ):
        tp = tn = positives = negatives = 0
        for session in assessed:
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

        def rate(successes, total):
            if not total:
                return {"value": None, "ci": None, "n": 0}
            ci = stats.binomtest(successes, total).proportion_ci(method="exact")
            return {"value": successes / total, "ci": [ci.low, ci.high], "n": total}

        report["signals"][signal] = {
            "sensitivity": rate(tp, positives),
            "specificity": rate(tn, negatives),
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
