"""The study's ethics package: one Markdown document, generated from the
protocol alone (FR-AGENT-5, FR-ETH-4).

An ethics committee reads five things about a study, every time: what
participants are asked to do, what is captured about them, in exactly what
words they are asked to consent, how their privacy is protected, and how they
withdraw. All five already exist as protocol-derived facts elsewhere in the
platform — the consent statement (:func:`enrollment.consent_statement`), the
content-policy descriptions (:mod:`agent_capture.redact`), the leg summaries
(:func:`enrollment.leg_summary`), the declared tasks
(:func:`protocol.assignment.tasks_of`). This module composes them into the
one document a researcher actually has to submit, rather than asking them to
assemble it by hand from five different platform surfaces.

Deterministic and pure, like every other protocol-derived artifact here: the
same protocol always produces the same package, byte for byte, with no model
in the loop. A field the protocol has not filled is named as missing — the
same honesty :func:`compiler.unresolved_slots` applies to the draft applies
here to the document a committee will actually read. An ethics package with a
placeholder in it is worse than one that says plainly what is not yet decided.
"""

from __future__ import annotations

from protocol.assignment import tasks_of

from middleware.enrollment import consent_statement, leg_summary


def _missing(label: str) -> str:
    return f"*[not yet specified: {label}]*"


def _overview(protocol: dict) -> list[str]:
    study = protocol.get("study") or {}
    title = study.get("title") or _missing("study title")
    researchers = study.get("researchers") or []
    ethics_ref = study.get("ethicsRef") or _missing("ethics approval reference")
    lines = [f"# Ethics package: {title}", ""]
    if researchers:
        lines.append(f"**Researchers:** {', '.join(researchers)}  ")
    lines.append(f"**Ethics reference:** {ethics_ref}  ")
    lines.append("")
    rqs = protocol.get("researchQuestions") or []
    if rqs:
        lines.append("## Research questions")
        lines.append("")
        for rq in rqs:
            lines.append(f"- {rq.get('text', '')}")
        lines.append("")
    return lines


def _design_summary(protocol: dict) -> list[str]:
    participants = protocol.get("participants") or {}
    session = protocol.get("session") or {}
    conditions = protocol.get("conditions") or []
    planned = participants.get("planned")
    design = participants.get("design") or _missing("within- or between-subjects")
    counterbalanced = participants.get("counterbalanced")
    duration = session.get("durationMinutes")

    lines = ["## Study design", ""]
    lines.append(
        f"- **Participants:** {planned if planned else _missing('planned N')}"
    )
    lines.append(f"- **Design:** {design}")
    if design == "within-subjects":
        cb = (
            "counterbalanced" if counterbalanced else "fixed order, not counterbalanced"
        )
        lines.append(f"- **Condition order:** {cb}")
    lines.append(
        "- **Conditions:** "
        + (", ".join(conditions) if conditions else _missing("conditions"))
    )
    lines.append(
        "- **Session length:** "
        + (f"{duration} minutes" if duration else _missing("session duration"))
    )
    lines.append("")
    return lines


def _tasks_section(protocol: dict) -> list[str]:
    tasks = tasks_of(protocol)
    lines = ["## What participants do", ""]
    for i, task in enumerate(tasks, 1):
        title = task.get("title") or task.get("id", f"Task {i}")
        lines.append(f"### {i}. {title}")
        description = task.get("description")
        if description:
            lines.append("")
            lines.append(description)
        detail = []
        if task.get("minutes"):
            detail.append(f"~{task['minutes']} minutes")
        if task.get("materials"):
            detail.append(f"materials: {task['materials']}")
        allowed = task.get("conditions")
        if allowed:
            detail.append(f"runs under: {', '.join(allowed)}")
        if detail:
            lines.append("")
            lines.append(" · ".join(detail))
        lines.append("")
    return lines


#: How each leg's state reads in a document a participant or a committee
#: will actually read - "unavailable" (the protocol names no instrument for
#: this leg at all) and "disabled" (declared, explicitly switched off) are
#: different facts, and collapsing them would understate what the study
#: could capture if reconfigured versus what it simply does not touch.
_STATE_TEXT = {
    "enabled": "active",
    "disabled": "declared, switched off",
    "unavailable": "not part of this study",
}


def _capture_section(protocol: dict) -> list[str]:
    lines = ["## What is captured", ""]
    lines.append(
        "Every instrument below records aggregates, shapes, and timings — "
        "never raw code content, keystrokes, or clipboard text."
    )
    lines.append("")
    for leg in leg_summary(protocol):
        state = _STATE_TEXT[leg["state"]]
        lines.append(f"- **{leg['label']}** ({state}): {leg['description']}")
    lines.append("")
    return lines


def _consent_section(protocol: dict) -> list[str]:
    conditions = protocol.get("conditions") or []
    lines = ["## Informed consent statement", ""]
    if not conditions:
        lines.append(_missing("conditions — consent text is generated per condition"))
        lines.append("")
        return lines
    lines.append(
        "The text below is shown to every participant before their session "
        "begins, and pairing cannot proceed without it (FR-INST-21). One "
        "version per condition, since the instruments a participant meets "
        "can differ by condition."
    )
    lines.append("")
    for condition in conditions:
        lines.append(f"**{condition} condition:**")
        lines.append("")
        lines.append(f"> {consent_statement(protocol, condition)}")
        lines.append("")
    return lines


def _withdrawal_section() -> list[str]:
    return [
        "## Withdrawal",
        "",
        "A participant may stop a session at any time, from within the "
        "editor, with no explanation required. Data already collected up to "
        "that point is retained unless the participant separately requests "
        "its deletion; nothing further is captured after the session ends.",
        "",
    ]


def build_ethics_package(protocol: dict) -> str:
    """The complete package, as one Markdown document.

    Pure function of the protocol: no database, no clock, no model. Suitable
    to attach to an IRB/ethics submission directly, or to adapt into the
    institution's own template — this is the platform's honest account of
    what the study does, not a substitute for the form your institution
    requires.
    """
    sections = [
        *_overview(protocol),
        *_design_summary(protocol),
        *_tasks_section(protocol),
        *_capture_section(protocol),
        *_consent_section(protocol),
        *_withdrawal_section(),
    ]
    return "\n".join(sections).rstrip() + "\n"
