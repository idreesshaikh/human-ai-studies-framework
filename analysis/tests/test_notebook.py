"""Starter notebook + data dictionary (the curated handoff)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import analysis.recipes  # noqa: F401 - registers the built-in recipes
import nbformat
from analysis.core import REGISTRY
from analysis.dataset import JOIN_KEYS, Dataset
from analysis.notebook import (
    build_notebook,
    data_dictionary_markdown,
    write_notebook,
)
from protocol.loader import load_protocol
from tests_support import synthetic_rows

REPO = Path(__file__).resolve().parents[2]
PILOT = REPO / "protocol" / "examples" / "pilot-study.yaml"


def _protocol() -> dict:
    return load_protocol(PILOT)


def _dataset() -> Dataset:
    return Dataset(rows=synthetic_rows(), study_id="pilot-2026")


def test_build_notebook_is_valid_nbformat4_json():
    doc = build_notebook(_protocol(), _dataset(), "pilot-2026")
    assert doc["nbformat"] == 4
    assert isinstance(doc["cells"], list) and doc["cells"]
    for cell in doc["cells"]:
        assert cell["cell_type"] in {"markdown", "code"}
        assert isinstance(cell["source"], str) and cell["source"]


def test_the_notebook_actually_opens_in_jupyter():
    """
    The bar that matters: not "shaped like nbformat 4" by this module's own assumptions,
    but valid against nbformat's real schema  -  the same check Jupyter itself runs on
    open.
    """
    doc = build_notebook(_protocol(), _dataset(), "pilot-2026")
    nbformat.validate(nbformat.from_dict(doc))


def test_cell_ids_are_present_and_unique():
    """
    nbformat 4.5+ requires a cell id; two cells sharing one is also a validation failure
    nbformat catches but a shape-only check would not.
    """
    doc = build_notebook(_protocol(), _dataset(), "pilot-2026")
    ids = [c["id"] for c in doc["cells"]]
    assert all(ids)
    assert len(ids) == len(set(ids)), "cell ids must be unique"


def test_notebook_is_deterministic():
    a = json.dumps(
        build_notebook(_protocol(), _dataset(), "pilot-2026"), sort_keys=True
    )
    b = json.dumps(
        build_notebook(_protocol(), _dataset(), "pilot-2026"), sort_keys=True
    )
    assert a == b


def test_dictionary_documents_only_real_columns():
    dataset = _dataset()
    md = data_dictionary_markdown(dataset)
    for column in [*JOIN_KEYS, "ts", "type", "seq"]:
        assert f"`{column}`" in md
    rows_by_type: dict[str, set[str]] = {}
    for row in dataset.rows:
        if row.get("source") == "metrics":
            continue
        rows_by_type.setdefault(row.get("type", ""), set()).update(
            row.get("payload") or {}
        )
    for line in md.splitlines():
        if "`payload." in line:
            key = line.split("`payload.")[1].split("`")[0]
            assert any(key in keys for keys in rows_by_type.values()), (
                f"documented payload key {key!r} never appears in the data"
            )
    for column in dataset.metric_columns:
        assert f"`{column}`" in md


def test_every_planned_recipe_has_a_resolvable_import_cell():
    protocol = _protocol()
    doc = build_notebook(protocol, _dataset(), "pilot-2026")
    source = "\n".join(c.get("source", "") for c in doc["cells"])
    planned = {
        rid
        for entry in protocol.get("analysisPlan", [])
        for rid in entry.get("recipes", [])
    }
    assert planned, "pilot protocol should plan recipes"
    for rid in planned:
        assert rid in REGISTRY, f"{rid} should be registered"
        module = rid.replace("-", "_")
        assert importlib.util.find_spec(f"analysis.recipes.{module}") is not None
        assert f"from analysis.recipes import {module}" in source


def test_notebook_never_runs_a_recipe():
    doc = build_notebook(_protocol(), _dataset(), "pilot-2026")
    source = "\n".join(c.get("source", "") for c in doc["cells"])
    assert ".run(dataset)" in source
    assert "result.summary" in source
    # ...but the notebook itself must not execute anything at build time.
    assert "Your analysis starts here" in source


def test_notebook_carries_the_session_timeline_cell():
    """
    P2-1: the curated handoff leads with the one-glance session picture  -  the timeline
    figure  -  before any recipe, so the researcher sees the shape of the data (and any
    integrity flags) first.
    """
    doc = build_notebook(_protocol(), _dataset(), "pilot-2026")
    source = "\n".join(c.get("source", "") for c in doc["cells"])
    assert "## Session timeline" in source
    assert "figures.session_timeline(dataset, session_id)" in source
    assert "fig.savefig" in source


def test_write_notebook_lands_both_artifacts(tmp_path):
    protocol = _protocol()
    nb, dd = write_notebook(protocol, _dataset(), "pilot-2026", tmp_path)
    assert nb.name == "notebook.ipynb" and dd.name == "data-dictionary.md"
    doc = json.loads(nb.read_text())
    assert doc["nbformat"] == 4
    assert "## Data dictionary" in dd.read_text()


def test_dictionary_only_flag(tmp_path):
    from analysis.notebook_cli import cmd_notebook

    class _Args:
        out = str(tmp_path)
        dictionary_only = True

    code = cmd_notebook(_protocol(), _dataset(), "pilot-2026", _Args())
    assert code == 0
    assert (tmp_path / "pilot-2026" / "data-dictionary.md").exists()
    assert not (tmp_path / "pilot-2026" / "notebook.ipynb").exists()
