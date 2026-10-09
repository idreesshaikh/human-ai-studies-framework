"""A factual design record; no validity score and no pooling judgement."""

import json

from protocol.measures import normalized_measures
from protocol.versioning import provenance


def design_card(
    protocol: dict,
    *,
    plan: dict | None = None,
    audit: dict | None = None,
    decisions: dict | None = None,
    rows: list[dict] | None = None,
    lineage: dict | None = None,
) -> dict:
    snapshots = [
        {
            "sessionId": r.get("sessionId"),
            "date": r.get("ts"),
            "versions": r.get("payload", {}),
        }
        for r in rows or []
        if r.get("type") == "environment_snapshot"
        and not r.get("payload", {}).get("synthetic")
    ]
    return {
        "formatVersion": 1,
        "study": protocol.get("study"),
        "provenance": provenance(protocol),
        "participants": protocol.get("participants"),
        "conditions": protocol.get("conditions"),
        "plannedPower": plan,
        "analysisFixedInAdvance": protocol.get("analysisPlan", []),
        "measures": normalized_measures(protocol),
        "instruments": protocol.get("instruments", {}).get("surveys", []),
        "sessionVersions": snapshots,
        "audit": audit
        or {"sessions": [], "accuracy": "Not measured", "status": "not-run"},
        "inclusionDecisions": decisions or {},
        "lineage": lineage
        or (
            {"rerunOf": protocol["rerunOf"], "pooled": False}
            if protocol.get("rerunOf")
            else None
        ),
        "pooling": "No automatic pooling",
        "interpretation": "Reports recorded information; does not rate validity.",
    }


def design_card_markdown(card: dict) -> str:
    lines = [
        f"# Design card: {(card.get('study') or {}).get('title', '')}",
        "",
        card["interpretation"],
        "",
    ]
    for title, key in (
        ("Provenance and lineage", "provenance"),
        ("Planned power and assumptions", "plannedPower"),
        ("Analysis fixed in advance", "analysisFixedInAdvance"),
        ("Measures", "measures"),
        ("Instruments and wording", "instruments"),
        ("Session tool versions", "sessionVersions"),
        ("Control-arm audit", "audit"),
        ("Inclusion decisions", "inclusionDecisions"),
        ("Re-run comparison", "lineage"),
    ):
        lines += [
            f"## {title}",
            "",
            "```json",
            json.dumps(card.get(key), indent=2, sort_keys=True, ensure_ascii=False),
            "```",
            "",
        ]
    lines += [card["pooling"], ""]
    return "\n".join(lines)
