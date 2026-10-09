"""Build source-disjoint splits and seal the independently annotated test rows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from measure_mapping import data

WORKTREE = Path(__file__).resolve().parents[3]


def make_splits(rows: list[dict], classes: set[str], *, seed: int = 20261008) -> dict:
    rows = data.validate_rows(rows, classes)
    forced = {row["group"] for row in rows if row["provenance"] in {"repo", "llm"}}
    independent = {
        row["id"]: row["group"] for row in rows if row["group"] not in forced
    }
    splits = data.assign_splits(independent, seed=seed)
    splits.update({row["id"]: "train" for row in rows if row["group"] in forced})
    leaks = data.leaky_pairs({row["id"]: row["text"] for row in rows}, splits)
    removed = set()
    for first, second in leaks:
        if "train" not in {splits[first], splits[second]}:
            raise data.DatasetError(
                f"near-duplicate calibration/test phrases: {first}, {second}"
            )
        removed.add(first if splits[first] == "train" else second)
    splits = {
        item: split for item, split in sorted(splits.items()) if item not in removed
    }
    test = [row for row in rows if splits.get(row["id"]) == "test"]
    return {
        "splits": splits,
        "testDigest": data.lock_digest(test),
        "removed": sorted(removed),
    }


def write_splits(
    rows: list[dict],
    classes: set[str],
    output: Path,
    sealed_test: Path,
    *,
    seed: int = 20261008,
    worktree: Path = WORKTREE,
) -> dict:
    if sealed_test.resolve().is_relative_to(worktree.resolve()):
        raise data.DatasetError("the sealed test file must be outside the working tree")
    result = make_splits(rows, classes, seed=seed)
    partition = {split: [] for split in data.SPLITS}
    for row in sorted(rows, key=lambda row: row["id"]):
        split = result["splits"].get(row["id"])
        if split is None:
            continue
        if split != "train" and (
            row.get("adjudicated") is not True
            or not row.get("annotator")
            or not row.get("annotator2")
            or row["annotator"] == row["annotator2"]
        ):
            raise data.DatasetError(
                f"{row['id']}: evaluation needs adjudication "
                "by two independent annotators"
            )
        partition[split].append({**row, "split": split})
    if not all(partition.values()):
        raise data.DatasetError("each split must contain at least one retained item")
    if output.exists() or sealed_test.exists():
        raise FileExistsError("a split revision cannot overwrite existing files")
    output.mkdir(parents=True)
    sealed_test.parent.mkdir(parents=True, exist_ok=True)
    for split in data.SPLITS:
        path = sealed_test if split == "test" else output / f"{split}.jsonl"
        with path.open("x") as file:
            for row in partition[split]:
                file.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")
    (output / "split.v1.json").write_text(json.dumps(result["splits"], indent=2) + "\n")
    (output / "test.locked.sha256").write_text(result["testDigest"] + "\n")
    (output / "removed.json").write_text(json.dumps(result["removed"], indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sealed-test", type=Path, required=True)
    args = parser.parse_args()
    rows = [
        json.loads(line) for line in args.rows.read_text().splitlines() if line.strip()
    ]
    classes = {row["id"] for row in json.loads(args.catalog.read_text())}
    result = write_splits(rows, classes, args.output, args.sealed_test)
    print(json.dumps({"retained": len(result["splits"]), "removed": result["removed"]}))


if __name__ == "__main__":
    main()
