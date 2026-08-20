"""The evolution engine: the deterministic core behind mid-study amendments."""

from __future__ import annotations

CONSENT_SUBKEYS: frozenset[str] = frozenset(
    {"contentPolicy", "capture", "redaction", "record", "scopes", "raw", "adapter"}
)


def _instruments(protocol: dict) -> dict:
    got = protocol.get("instruments") or {}
    return got if isinstance(got, dict) else {}


def consent_relevance(before: dict, after: dict) -> tuple[bool, list[str]]:
    """Decide whether the change from ``before`` to ``after`` is consent-relevant."""
    reasons: list[str] = []

    before_instr = _instruments(before)
    after_instr = _instruments(after)

    for name in sorted(set(after_instr) - set(before_instr)):
        reasons.append(f"adds a new data stream: instruments.{name}")
    for name in sorted(set(before_instr) - set(after_instr)):
        reasons.append(f"removes a data stream: instruments.{name}")

    for name in sorted(set(before_instr) & set(after_instr)):
        b = before_instr.get(name) or {}
        a = after_instr.get(name) or {}
        b = b if isinstance(b, dict) else {}
        a = a if isinstance(a, dict) else {}
        for key in sorted(CONSENT_SUBKEYS):
            if (key in b or key in a) and b.get(key) != a.get(key):
                reasons.append(
                    f"changes the content policy of instruments.{name} "
                    f"({key}: {b.get(key)!r} → {a.get(key)!r})"
                )

    for name in sorted(set(before_instr) & set(after_instr)):
        if _enabled_changed(before_instr.get(name) or {},
                           after_instr.get(name) or {}, name, reasons):
            pass

    for name in sorted(set(before_instr) & set(after_instr)):
        b = before_instr.get(name) or {}
        a = after_instr.get(name) or {}
        if not isinstance(b, dict) or not isinstance(a, dict):
            continue
        for subkey in sorted(set(a) - set(b)):
            reasons.append(
                f"adds a new metric subtree to instruments.{name}: {subkey}"
            )

    for section in ("ethics", "consent"):
        if before.get(section) != after.get(section) and (
            before.get(section) is not None or after.get(section) is not None
        ):
            reasons.append(f"changes the {section} scope of the study")

    b_cur = before.get("curated") or {}
    a_cur = after.get("curated") or {}
    if not b_cur and a_cur:
        reasons.append("adds a curated data source")
    elif b_cur and a_cur and b_cur.get("source") != a_cur.get("source"):
        reasons.append(
            f"changes the curated data source "
            f"({b_cur.get('source')!r} → {a_cur.get('source')!r})"
        )

    b_agents = (before.get("participants") or {}).get("agents")
    a_agents = (after.get("participants") or {}).get("agents")
    if not b_agents and a_agents:
        reasons.append("enrolls agent participants (a new data source)")

    return (bool(reasons), sorted(reasons))


def _enabled_changed(
    before: dict, after: dict, prefix: str, reasons: list
) -> bool:
    """
    Recursively walk two dicts — if any ``enabled`` field differs at any depth, append a
    reason and return True.
    """
    changed = False
    for key in sorted(set(before) | set(after)):
        bv = before.get(key)
        av = after.get(key)
        path = f"{prefix}.{key}"
        if key == "enabled" and not isinstance(bv, dict) and not isinstance(av, dict):
            if bv != av:
                reasons.append(
                    f"changes capture state of {prefix} "
                    f"({key}: {bv!r} → {av!r})"
                )
                changed = True
        elif isinstance(bv, dict) and isinstance(av, dict):
            if _enabled_changed(bv, av, path, reasons):
                changed = True
        elif isinstance(bv, dict) or isinstance(av, dict):
            reasons.append(f"changes the structure of {path}")
            changed = True
    return changed


def change_summary(before: dict, after: dict) -> list[str]:
    """
    A plain-language, deterministic list of what the amendment changed — the neutral
    "what" the ethics-board delta and the amendment banner render.
    """
    lines: list[str] = []

    b_rq = {rq.get("text", "") for rq in before.get("researchQuestions", [])}
    a_rq = {rq.get("text", "") for rq in after.get("researchQuestions", [])}
    for t in sorted(a_rq - b_rq):
        lines.append(f"adds research question: {t}")
    for t in sorted(b_rq - a_rq):
        lines.append(f"removes research question: {t}")

    b_cond = set(before.get("conditions", []))
    a_cond = set(after.get("conditions", []))
    for c in sorted(a_cond - b_cond):
        lines.append(f"adds condition: {c}")
    for c in sorted(b_cond - a_cond):
        lines.append(f"removes condition: {c}")

    b_instr, a_instr = _instruments(before), _instruments(after)
    for name in sorted(set(a_instr) - set(b_instr)):
        lines.append(f"adds instrument: {name}")
    for name in sorted(set(b_instr) - set(a_instr)):
        lines.append(f"removes instrument: {name}")
    for name in sorted(set(b_instr) & set(a_instr)):
        if b_instr[name] != a_instr[name]:
            lines.append(f"reconfigures instrument: {name}")

    b_p, a_p = before.get("participants", {}), after.get("participants", {})
    if b_p.get("planned") != a_p.get("planned"):
        lines.append(
            f"changes planned participants: {b_p.get('planned')} → {a_p.get('planned')}"
        )
    if b_p.get("design") != a_p.get("design"):
        lines.append(f"changes design: {b_p.get('design')} → {a_p.get('design')}")

    return lines


def amendment_summary_doc(
    *,
    study_id: str,
    from_version: int,
    to_version: int,
    rationale: str,
    changes: list[str],
    consent_relevant: bool,
    consent_reasons: list[str],
    grounding: list[str],
    approved_by: str,
    approved_at: str,
) -> str:
    """
    Render the ethics-board amendment delta as Markdown — the document S1 actually sends
    to S3.
    """
    out: list[str] = []
    out.append(
        f"# Amendment to study protocol (revision {from_version} → {to_version})"
    )
    out.append("")
    out.append(f"- **Study:** {study_id}")
    out.append(f"- **Approved by:** {approved_by or 'not recorded'}")
    out.append(f"- **Date:** {approved_at or 'not recorded'}")
    out.append("")
    out.append("## What changed")
    out.append("")
    if changes:
        out.extend(f"- {c}" for c in changes)
    else:
        out.append("- (no structural change detected in the compiled draft)")
    out.append("")
    out.append("## Why")
    out.append("")
    out.append(rationale.strip() or "_No rationale recorded._")
    out.append("")
    out.append("## Consent impact")
    out.append("")
    if consent_relevant:
        out.append(
            "**This amendment is consent-relevant.** New data-collection "
            "sessions are paused until an updated ethics approval is uploaded. "
            "Already-collected data and any in-progress sessions are untouched."
        )
        out.append("")
        out.append("Reasons the consent rule fired:")
        out.extend(f"- {r}" for r in consent_reasons)
    else:
        out.append(
            "This amendment is **not** consent-relevant: it changes no data "
            "stream, content policy, or ethics scope. It applies from the next "
            "session; running sessions are unaffected."
        )
    out.append("")
    out.append("## Grounding")
    out.append("")
    if grounding:
        out.extend(f"- {g}" for g in grounding)
    else:
        out.append("- _unsourced: the amendment carries no citations_")
    out.append("")
    return "\n".join(out)
