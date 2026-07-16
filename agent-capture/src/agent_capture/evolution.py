"""Code-evolution / process metrics (FR-INST-17), derived at session end.

Joins the workspace-snapshot LOC series (FR-INST-15) with origin-classified
edit bursts (FR-INST-10) into the code leg's literature-standard units - the
metrics LLM-assistant studies most often report (SLR arXiv:2507.03156;
Ziegler et al. arXiv:2205.06537):

- **gross / net LOC** added and deleted over the session (from the snapshot
  ``insertions``/``deletions`` series),
- within-session **churn** - lines added then removed before session end, and
- **AI-code persistence** - Ziegler's second measure, the share of AI-origin
  insertions surviving to session end.

Honesty note carried into the payload: persistence and churn are
**char-approximated** here. Line-level persistence needs ``edit_burst``
``startLine``/``endLine`` (a schema-v4 extension change deferred out of this
phase, `requirements/traceability.md`); until then a recipe must state the
approximation in its methods, exactly as the metric-coverage review requires.

Emitted as a single ``derived: true`` ``code_evolution`` event per session
(a recipe-level consumer lands in MP-09/later; the derivation is the leg's
job here).
"""

from __future__ import annotations

from agent_capture.events import (
    EVENT_CODE_EVOLUTION,
    SOURCE_DERIVED,
    Keys,
    study_event,
)


def _sum(events: list[dict], type_: str, field: str, *, where=None) -> int:
    total = 0
    for e in events:
        if e.get("type") != type_:
            continue
        p = e.get("payload", {})
        if where is not None and not where(p):
            continue
        total += int(p.get(field, 0) or 0)
    return total


def compute_evolution(events: list[dict]) -> dict:
    """The ``code_evolution`` payload for one session's events."""
    gross_ins = _sum(events, "workspace_snapshot", "insertions")
    gross_del = _sum(events, "workspace_snapshot", "deletions")

    ai = lambda p: p.get("origin") == "ai"  # noqa: E731
    paste = lambda p: p.get("origin") == "paste"  # noqa: E731
    ai_added = _sum(events, "edit_burst", "charsAdded", where=ai)
    ai_deleted = _sum(events, "edit_burst", "charsDeleted", where=ai)
    paste_added = _sum(events, "edit_burst", "charsAdded", where=paste)
    total_added = _sum(events, "edit_burst", "charsAdded")

    commits = sum(1 for e in events if e.get("type") == "git_commit")

    ai_persistence = (
        (ai_added - ai_deleted) / ai_added if ai_added > 0 else None
    )
    ai_share = ai_added / total_added if total_added > 0 else None

    return {
        "grossLocInserted": gross_ins,
        "grossLocDeleted": gross_del,
        "netLoc": gross_ins - gross_del,
        "churnLinesApprox": gross_del,  # within-session removals; approx
        "aiCharsInserted": ai_added,
        "pasteCharsInserted": paste_added,
        "totalCharsInserted": total_added,
        "aiInsertionShare": ai_share,
        "aiPersistenceApprox": ai_persistence,
        "participantCommits": commits,
        "approximation": (
            "churn and AI persistence are char-approximated; line-level "
            "awaits edit_burst startLine/endLine (schema v4)."
        ),
        "derived": True,
    }


def derive_evolution(events: list[dict], keys: Keys) -> dict | None:
    """One ``code_evolution`` StudyEvent, or ``None`` when the session has no
    snapshots or bursts to derive from."""
    has_inputs = any(
        e.get("type") in ("workspace_snapshot", "edit_burst", "git_commit")
        for e in events
    )
    if not has_inputs:
        return None
    return study_event(
        keys,
        source=SOURCE_DERIVED,
        seq=1_000,  # separate band from correlation's ordinal seqs
        type=EVENT_CODE_EVOLUTION,
        payload=compute_evolution(events),
    )
