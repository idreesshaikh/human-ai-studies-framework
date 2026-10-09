"""Traceable repository phrases with model-drafted labels for training only."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import yaml
from protocol.measures import shipped_instruments

MEASURES = {
    "fatigue-by-condition": ("E3", None),
    "perceived-load": ("E3", None),
    "task-accuracy": ("E2", None),
    "completion-time": ("E1", None),
    "first-green-time": ("E1", None),
    "task-time": ("E1", None),
    "collaboration-pattern": ("E9", None),
    "struggle-episodes": ("E4", None),
    "paste-provenance": ("E5", None),
    "binary-outcome": ("E2", None),
    "acceptance-rate": ("E8", None),
    "latency": ("E7", None),
    "workload": ("S8", None),
}
SURVEY_ITEMS = {
    "mental_demand": "S1",
    "effort": "S2",
    "frustration": "S3",
    "time_pressure": "S4",
    "temporal_demand": "S4",
    "perceived_performance": "S5",
    "performance": "S5",
    "comprehension": "S6",
    "physical_demand": "S7",
}


def build_seed(root: Path) -> tuple[list[dict], list[str]]:
    rows, unresolved = [], []

    def add(group, key, text, label, secondary, source, reason, confidence):
        ident = hashlib.sha256(f"{group}:{key}".encode()).hexdigest()[:20]
        rows.append(
            {
                "id": ident,
                "text": text,
                "label": label,
                "secondary_label": secondary,
                "source": "template"
                if source.startswith("templates/")
                else "instrument",
                "source_ref": source,
                "provenance": "repo",
                "labelProvenance": "llm-draft",
                "group": group,
                "catalog_version": "v1-proposed",
                "split": "train",
                "adjudicated": False,
                "confidence": confidence,
                "reason": reason,
            }
        )

    for path in sorted((root / "templates/registry").glob("*.yaml")):
        template = yaml.safe_load(path.read_text())
        group = template["templateId"]
        for measure in template["measures"]:
            key = measure["id"]
            text = measure.get("description") or key
            label, secondary = MEASURES.get(key, ("none", None))
            reason = (
                f"Proposed construct match for template measure {key}; "
                "capture compatibility requires separate review."
            )
            confidence = 2
            if key == "primary-outcome" and group in {
                "two-group-rct-v1",
                "within-subjects-crossover-v1",
            }:
                label, secondary = "E1", "E2"
                reason = (
                    "Explicit task time and correctness; "
                    "time is primary, correctness secondary."
                )
            elif label == "none":
                reason = (
                    "Generic outcome, unsupported quantity, "
                    "or unspecified self-report instrument."
                )
                confidence = 1
                unresolved.append(f"{group}:{key}: {text}")
            add(
                group,
                key,
                text,
                label,
                secondary,
                f"{path.relative_to(root)}#measures.{key}",
                reason,
                confidence,
            )

    for instrument in shipped_instruments():
        group = instrument["id"]
        for item in instrument["items"]:
            label = SURVEY_ITEMS.get(item["id"])
            if group == "sus":
                label = "S9"
            elif group == "pre-task-skill":
                label = "S10"
            add(
                group,
                item["id"],
                item["text"],
                label or "none",
                None,
                f"protocol/src/protocol/schema/survey-instruments.json#{group}.{item['id']}",
                "Declared item match; individual SUS/skill items represent their "
                "parent construct, not a validated standalone score.",
                3,
            )
    # Recipe titles naming only tests/designs are methods, not measured quantities.
    # They are intentionally excluded instead of being given fabricated constructs.
    return rows, unresolved


if __name__ == "__main__":
    base = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=base.parents[1])
    parser.add_argument("--out", type=Path, default=base / "data/seed")
    args = parser.parse_args()
    rows, unresolved = build_seed(args.root)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "seed.v1.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    )
    (args.out / "unmapped.txt").write_text("\n".join(unresolved) + "\n")
    print(
        json.dumps(
            {
                "draftRows": len(rows),
                "classes": dict(Counter(r["label"] for r in rows)),
                "needsReview": len(unresolved),
            },
            indent=2,
        )
    )
