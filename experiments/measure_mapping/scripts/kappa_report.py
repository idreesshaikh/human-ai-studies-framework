"""Report independent annotation agreement, retaining none and missingness."""

import argparse
import csv
import json
from pathlib import Path

from measure_mapping.metrics import cluster_bootstrap, cohen_kappa


def agreement_report(first: dict, second: dict, groups: dict | None = None) -> dict:
    if not first or set(first) != set(second):
        raise ValueError("both annotators must label the same non-empty set of items")
    if any(
        not str(value or "").strip() for value in [*first.values(), *second.values()]
    ):
        raise ValueError("annotations are incomplete")
    ids = sorted(first)

    def summary(selected):
        a, b = [first[item] for item in selected], [second[item] for item in selected]
        kappa = cohen_kappa(a, b) if selected and len(set(a) | set(b)) > 1 else None
        interval = None
        interval_reason = "no groups supplied"
        if groups is not None and kappa is not None:
            if len({groups[item] for item in selected}) < 2:
                interval_reason = "fewer than two independent clusters"
            else:
                try:
                    interval = cluster_bootstrap(
                        lambda idx: cohen_kappa(
                            [a[i] for i in idx], [b[i] for i in idx]
                        ),
                        [groups[item] for item in selected],
                    )
                    interval_reason = None
                except ValueError as exc:
                    interval_reason = str(exc)
        elif kappa is None:
            interval_reason = "kappa is undefined"
        return {
            "n": len(selected),
            "kappa": kappa,
            "interval": interval,
            "interval_reason": interval_reason,
            "agreement": sum(x == y for x, y in zip(a, b, strict=True)) / len(a)
            if a
            else None,
        }

    classes = sorted(set(first.values()) | set(second.values()))
    confusion = {a: dict.fromkeys(classes, 0) for a in classes}
    for item in ids:
        confusion[first[item]][second[item]] += 1
    with_none = summary(ids)
    without_none = summary(
        [item for item in ids if first[item] != "none" and second[item] != "none"]
    )
    return {
        "with_none": with_none,
        "without_none": without_none,
        "without_none_definition": "both annotations differ from none",
        "confusion": confusion,
        "per_class_raw_agreement": {
            label: sum(
                (first[item] == label) == (second[item] == label) for item in ids
            )
            / len(ids)
            for label in classes
        },
        "gate_passed": len(ids) >= 100
        and with_none["kappa"] is not None
        and with_none["kappa"] >= 0.6,
    }


def read_sheet(path: Path) -> dict:
    with path.open(newline="") as file:
        rows = list(csv.DictReader(file))
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("duplicate item ids in annotation sheet")
    return {row["id"]: row["label"].strip() for row in rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument(
        "--data",
        type=Path,
        required=True,
        help="source JSONL with paper/cluster groups",
    )
    args = parser.parse_args()
    rows = [
        json.loads(line) for line in args.data.read_text().splitlines() if line.strip()
    ]
    groups = {row["id"]: row["group"] for row in rows}
    print(
        json.dumps(
            agreement_report(read_sheet(args.first), read_sheet(args.second), groups),
            indent=2,
        )
    )
