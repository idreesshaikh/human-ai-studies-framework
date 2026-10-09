"""The proposed catalog names real fields and registered analysis recipes."""

import hashlib
import json
import re
from pathlib import Path

import analysis.recipes  # noqa: F401 -- populate the registry
from analysis.core import REGISTRY
from protocol.measures import shipped_instruments

BASE = Path(__file__).resolve().parents[1]


def test_proposed_catalog_has_supported_fields_recipes_and_a_recorded_digest():
    rows = json.loads((BASE / "catalog/catalog.v1.json").read_text())
    assert {row["id"] for row in rows} == {
        *(f"S{i}" for i in range(1, 11)),
        *(f"E{i}" for i in range(1, 11)),
    }
    assert len(rows) == 20
    instruments = {item["id"]: item for item in shipped_instruments()}
    for row in rows:
        assert (
            row["description"] and len(row["positives"]) == len(row["negatives"]) == 2
        )
        assert row["provenance"] == "llm" and row["reviewStatus"] == "proposed"
        for recipe in row["recipeByDesign"].values():
            assert recipe is None or recipe in REGISTRY
        for field in row["fields"]:
            assert re.fullmatch(r"[a-z_]+\.[A-Za-z0-9_.-]+", field)
            if row["instrument"] in instruments and ".responses." in field:
                ids = {item["id"] for item in instruments[row["instrument"]]["items"]}
                assert field.split(".responses.")[-1] in ids
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    assert (
        hashlib.sha256(canonical).hexdigest()
        == (BASE / "catalog/catalog.v1.sha256").read_text().strip()
    )
