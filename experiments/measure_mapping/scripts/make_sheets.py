"""Create two blind annotation sheets without copying any existing labels."""

import argparse
import csv
import json
from pathlib import Path

COLUMNS = (
    "id",
    "text",
    "label",
    "secondary_label",
    "confidence(1-3)",
    "none_reason",
    "note",
)


def make_sheets(source: Path, output: Path) -> tuple[Path, Path]:
    rows = [
        json.loads(line) for line in source.read_text().splitlines() if line.strip()
    ]
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("duplicate item ids")
    if any(not row.get("id") or not row.get("text") for row in rows):
        raise ValueError("each item needs an id and text")
    output.mkdir(parents=True, exist_ok=True)
    paths = output / "annotator-a.csv", output / "annotator-b.csv"
    for path in paths:
        if path.exists():
            raise FileExistsError(f"refusing to overwrite annotations: {path}")
    for path in paths:
        with path.open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows({"id": row["id"], "text": row["text"]} for row in rows)
    return paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    for path in make_sheets(args.data, args.out):
        print(path)
