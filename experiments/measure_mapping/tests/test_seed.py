"""Draft seed labels retain source locations and never enter evaluation splits."""

import json
from pathlib import Path

import pytest
import yaml
from measure_mapping import data
from scripts.build_seed import build_seed

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]


def test_all_templates_are_traceable_training_only_drafts(tmp_path):
    rows, unmapped = build_seed(ROOT)
    classes = {
        row["id"] for row in json.loads((BASE / "catalog/catalog.v1.json").read_text())
    }
    assert data.validate_rows(rows, classes)
    expected = {
        yaml.safe_load(path.read_text())["templateId"]
        for path in (ROOT / "templates/registry").glob("*.yaml")
    }
    assert expected <= {row["group"] for row in rows}
    assert len({row["id"] for row in rows}) == len(rows)
    assert all(row["provenance"] == "repo" and row["split"] == "train" for row in rows)
    assert all(row["labelProvenance"] == "llm-draft" and row["reason"] for row in rows)
    assert all(row["source_ref"] and not row["adjudicated"] for row in rows)
    assert unmapped
    with pytest.raises(data.DatasetError):
        data.validate_rows([{**rows[0], "split": "test"}], classes)
