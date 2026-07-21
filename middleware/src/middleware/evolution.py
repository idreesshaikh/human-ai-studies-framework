"""The evolution engine: the deterministic core behind
mid-study amendments and the platform's own feedback loop.

Everything here is a **pure function** — no LLM, no clock, no DB. The
conversation and compiler propose and produce; this module *classifies* and
*summarizes*, deterministically, so its every judgment is table-testable:

- :func:`consent_relevance` is *the rule* S3 relies on. Consent-relevance is
  never an LLM judgment: anything touching the ethics section, an instrument's
  content policy / capture scope, or introducing a new data stream (a new
  instrument, or a curated source) is consent-relevant, by rule (FR-CONV-4.2).
  A threshold or interval tweak inside an existing instrument is *not* — it
  applies from the next session with no re-approval (F4.2).
- :func:`change_summary` / :func:`amendment_summary_doc` generate the
  human-readable amendment delta S1 sends to the ethics board (FR-ANA-6 style:
  deterministic generation from the record, never a model's prose).
- :func:`stall_category`, :func:`accumulate_shapes` and :func:`draft_proposal`
  power the platform's self-application loop (FR-CONV-5): anonymous
  cross-project *shape* only, and an inert retrospective proposal that cites
  the findings and shapes it used.

A note on versioning. fixed the protocol document's ``protocolVersion``
field to a schema-shape enum [1, 2, 3] (v1 live human study, v2 + curated, v3
agent participants). The amendment counter FR-CONV-4 calls the "protocol
version" is therefore a *separate* study-revision integer, held in
``StudyEvolution.current_version`` and stamped onto each ``SessionOpen`` — the
value the version chips render. Bumping the YAML field per amendment would
break validation, so the record of "which revision a session ran under" lives
beside the protocol, not inside its schema field.
"""

from __future__ import annotations

#: Instrument sub-keys whose change alters *what is captured or how it is
#: retained* — the FR-ETH-2 consent surface. A change to any of these (or a
#: whole new instrument) is consent-relevant; a change to anything else inside
#: an instrument (a probe interval, a numeric threshold) is not (F4.2).
CONSENT_SUBKEYS: frozenset[str] = frozenset(
    {"contentPolicy", "capture", "redaction", "record", "scopes", "raw", "adapter"}
)


def _instruments(protocol: dict) -> dict:
    got = protocol.get("instruments") or {}
    return got if isinstance(got, dict) else {}


def consent_relevance(before: dict, after: dict) -> tuple[bool, list[str]]:
    """Decide whether the change from ``before`` to ``after`` is consent-relevant.

    Returns ``(relevant, reasons)`` where ``reasons`` is a sorted list of
    plain-language sentences (the amendment record quotes them verbatim, so the
    "why" is recorded, not re-derived). Deterministic and total: the same pair
    of protocols always yields the same verdict — this is the rule the
    table-driven test (change → relevant?) pins.

    Extended for FR-CONV-7: a change to any nested ``enabled`` field, or the
    first appearance of any previously-undeclared metric subtree, is also
    consent-relevant — because turning capture on/off for an instrument is
    functionally the same as adding/removing a data stream, and the old
    flat-subkey check missed it entirely.
    """
    reasons: list[str] = []

    before_instr = _instruments(before)
    after_instr = _instruments(after)

    # A new instrument is a new data stream (the paradigm consent-relevant
    # change: FR-CONV-4.2 "introducing a new data stream").
    for name in sorted(set(after_instr) - set(before_instr)):
        reasons.append(f"adds a new data stream: instruments.{name}")
    # Removing a stream narrows capture — still a change to the consented
    # instrument set S3 approved, so it is version-visible and gated too.
    for name in sorted(set(before_instr) - set(after_instr)):
        reasons.append(f"removes a data stream: instruments.{name}")

    # For instruments present in both, only a change to a consent-surface
    # sub-key (content policy, capture scope, redaction) is relevant; a
    # threshold/interval tweak is not (F4.2).
    for name in sorted(set(before_instr) & set(after_instr)):
        b = before_instr.get(name) or {}
        a = after_instr.get(name) or {}
        b = b if isinstance(b, dict) else {}
        a = a if isinstance(a, dict) else {}
        for key in sorted(CONSENT_SUBKEYS):
            if key in b or key in a:
                if b.get(key) != a.get(key):
                    reasons.append(
                        f"changes the content policy of instruments.{name} "
                        f"({key}: {b.get(key)!r} → {a.get(key)!r})"
                    )

    # FR-CONV-7: recursive ``enabled`` change check — turning capture on/off
    # at any nesting depth is consent-relevant.
    for name in sorted(set(before_instr) & set(after_instr)):
        if _enabled_changed(before_instr.get(name) or {},
                           after_instr.get(name) or {}, name, reasons):
            pass  # reasons already appended by helper

    # FR-CONV-7: first appearance of a previously-undeclared metric subtree
    # (e.g. a new top-level key inside an existing instrument) is consent-relevant.
    for name in sorted(set(before_instr) & set(after_instr)):
        b = before_instr.get(name) or {}
        a = after_instr.get(name) or {}
        if not isinstance(b, dict) or not isinstance(a, dict):
            continue
        for subkey in sorted(set(a) - set(b)):
            reasons.append(
                f"adds a new metric subtree to instruments.{name}: {subkey}"
            )

    # The ethics / consent subtree, whatever shape a template gives it, is a
    # consent surface in full — any change to it is relevant.
    for section in ("ethics", "consent"):
        if before.get(section) != after.get(section):
            if before.get(section) is not None or after.get(section) is not None:
                reasons.append(f"changes the {section} scope of the study")

    # A curated data source is a new data stream about (mined) strangers, who
    # get the same protection as consented participants (FR-ETH-2, wall 7).
    b_cur = before.get("curated") or {}
    a_cur = after.get("curated") or {}
    if not b_cur and a_cur:
        reasons.append("adds a curated data source")
    elif b_cur and a_cur and b_cur.get("source") != a_cur.get("source"):
        reasons.append(
            f"changes the curated data source "
            f"({b_cur.get('source')!r} → {a_cur.get('source')!r})"
        )

    # Agent participants are a new data source (FR-PROT-9): enrolling them
    # after ethics approval is consent-relevant.
    b_agents = (before.get("participants") or {}).get("agents")
    a_agents = (after.get("participants") or {}).get("agents")
    if not b_agents and a_agents:
        reasons.append("enrolls agent participants (a new data source)")

    return (bool(reasons), sorted(reasons))


def _enabled_changed(
    before: dict, after: dict, prefix: str, reasons: list
) -> bool:
    """Recursively walk two dicts — if any ``enabled`` field differs at any
    depth, append a reason and return True. FR-CONV-7."""
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
            # One side is a dict and the other isn't — structural change.
            reasons.append(f"changes the structure of {path}")
            changed = True
    return changed


def change_summary(before: dict, after: dict) -> list[str]:
    """A plain-language, deterministic list of what the amendment changed —
    the neutral "what" the ethics-board delta and the amendment banner render.
    Covers the sections a design conversation edits; ordering is stable.
    """
    lines: list[str] = []

    # Research questions (by text — ids are churny).
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
    """Render the ethics-board amendment delta as Markdown — the document S1
    actually sends to S3. Deterministic generation from the amendment record
    (FR-CONV-4.3, FR-ANA-6 style); no model writes this prose.
    """
    out: list[str] = []
    out.append(
        f"# Amendment to study protocol (revision {from_version} → {to_version})"
    )
    out.append("")
    out.append(f"- **Study:** {study_id}")
    out.append(f"- **Approved by:** {approved_by or '—'}")
    out.append(f"- **Date:** {approved_at or '—'}")
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
        out.append("- _unsourced — the amendment carries no citations_")
    out.append("")
    return "\n".join(out)


# ------------------------------------------------------- cross-project shapes
#
# Stall-point taxonomy seeded from ``stalled-biased-confused-rca`` (RCA of where
# conversations stall) and grown from observed shape. The taxonomy is a degree
# of freedom (aggregate shape, so iteration is cheap and safe); these are the
# seed buckets.

STALL_CATEGORIES: tuple[str, ...] = (
    "validation-error",  # a compile bounced with schema errors
    "unresolved-slots",  # mandatory sections still empty at compile
    "no-template",  # a bespoke draft never chose a template
    "none",  # a clean, complete compile
)


def stall_category(
    *, valid: bool, errors: list, unresolved: list, has_template: bool
) -> str:
    """Classify one compilation's stall shape (anonymous, no content). The
    first matching bucket wins — a validation error is the sharpest signal,
    then unresolved slots, then a template-less bespoke draft."""
    if errors:
        return "validation-error"
    if unresolved:
        return "unresolved-slots"
    if not has_template:
        return "no-template"
    return "none"


def accumulate_shapes(
    *,
    templates_chosen: list[str],
    unresolved_slots: list[str],
    stalls: list[str],
    rejected_move_kinds: list[str],
) -> list[tuple[str, str, int]]:
    """Fold raw per-project observations into ``(metric, key, count)`` shape
    rows. The inputs are *already anonymized* to vocabulary tokens (template
    ids, slot names, stall categories, move kinds) — this function never sees,
    and so never can leak, conversation text, protocol content, or a project
    identifier (FR-CONV-5.3, the property the grep-the-output test asserts).
    """
    from collections import Counter

    buckets: list[tuple[str, str, int]] = []
    for metric, values in (
        ("template-chosen", templates_chosen),
        ("slot-unresolved", unresolved_slots),
        ("conversation-stall", stalls),
        ("move-rejected", rejected_move_kinds),
    ):
        for key, count in sorted(Counter(values).items()):
            buckets.append((metric, key, count))
    return buckets


def draft_proposal(*, findings: list[dict], shapes: list[dict]) -> dict:
    """Draft an **inert** platform-improvement proposal (FR-CONV-5.2, extends
    FR-META-2). Cites the findings rows and aggregate shapes it used; lands as
    a draft for human review, exactly like every other platform-drafted
    artifact — nothing self-applies (the FR-META inert posture).

    Deterministic: the same findings + shapes always draft the same proposal.
    """
    feedback = [f for f in findings if f.get("kind") == "feedback"]
    by_kind: dict[str, list[dict]] = {}
    for f in feedback:
        locus = f.get("context", {}).get("conversationLocus", {})
        by_kind.setdefault(locus.get("kind", "unclassified"), []).append(f)

    stall_shapes = sorted(
        (s for s in shapes if s["metric"] == "conversation-stall"),
        key=lambda s: (-s["count"], s["key"]),
    )
    rejected_shapes = sorted(
        (s for s in shapes if s["metric"] == "move-rejected"),
        key=lambda s: (-s["count"], s["key"]),
    )

    items: list[dict] = []
    for kind in sorted(by_kind):
        rows = by_kind[kind]
        items.append(
            {
                "title": f"Address feedback theme: {kind}",
                "evidence": {
                    "findingIds": sorted(f["id"] for f in rows),
                    "count": len(rows),
                },
                "kind": "ux-defect",
            }
        )
    for shape in stall_shapes:
        if shape["key"] in ("none"):
            continue
        items.append(
            {
                "title": f"Reduce conversations that stall at: {shape['key']}",
                "evidence": {
                    "shape": shape["metric"],
                    "key": shape["key"],
                    "count": shape["count"],
                },
                "kind": "template-improvement"
                if shape["key"] == "unresolved-slots"
                else "ux-defect",
            }
        )
    for shape in rejected_shapes[:3]:
        items.append(
            {
                "title": f"Revisit frequently-rejected design move: {shape['key']}",
                "evidence": {
                    "shape": shape["metric"],
                    "key": shape["key"],
                    "count": shape["count"],
                },
                "kind": "template-improvement",
            }
        )

    return {
        "status": "draft",  # inert — a human approves; nothing self-applies
        "title": "Platform retrospective (drafted)",
        "generatedFrom": {
            "feedbackFindings": len(feedback),
            "shapeRows": len(shapes),
        },
        "citedFindingIds": sorted(f["id"] for f in feedback),
        "items": items,
    }
