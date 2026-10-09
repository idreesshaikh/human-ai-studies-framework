"""Starter notebook and data dictionary generation."""

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


def test_dictionary_distinguishes_synthetic_labels_from_measurements():
    rows = synthetic_rows()
    rows.append(
        {
            **rows[0],
            "source": "metrics",
            "type": "file_metrics",
            "payload": {"lines": 12},
        }
    )
    for row in rows:
        row.setdefault("payload", {})["synthetic"] = True
    dictionary = data_dictionary_markdown(Dataset(rows))
    assert "`payload.synthetic` | bool | simulated" in dictionary
    assert (
        "`synthetic` | bool | simulated metric row; not participant data" in dictionary
    )
    assert "`synthetic` | numeric" not in dictionary


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


def test_notebook_carries_the_session_timeline_cell():
    """
    P2-1: the starter notebook leads with the one-glance session picture  -  the
    timeline figure  -  before any recipe, so the researcher sees the shape of the
    data (and any integrity flags) first.
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
    nbformat.validate(nbformat.from_dict(doc))
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


def test_notebook_freezes_protocol_metadata_for_typed_recipe_execution(monkeypatch):
    dataset = _dataset()
    protocol = _protocol()
    notebook = build_notebook(protocol, dataset, "pilot-2026")
    setup = next(
        cell["source"]
        for cell in notebook["cells"]
        if "dataset = Dataset.from_json" in cell.get("source", "")
    )
    monkeypatch.setattr(Dataset, "from_json", classmethod(lambda cls, path: dataset))
    namespace = {}
    exec(setup, namespace)  # noqa: S102 - execute only the generated fixture cell
    assert namespace["dataset"].meta["protocol"] == protocol
    assert namespace["dataset"].meta["control_conditions"] == protocol.get(
        "controlConditions", []
    )


def test_notebook_states_how_many_sessions_were_excluded_and_never_opens_one():
    rows = synthetic_rows()
    first = rows[0]["sessionId"]
    for r in rows:
        if r["sessionId"] == first:
            r["pilot"] = True
    nb = build_notebook(
        _protocol(), Dataset(rows=rows, study_id="pilot-2026"), "pilot-2026"
    )
    text = "\n".join(c["source"] for c in nb["cells"])
    total = len({r["sessionId"] for r in rows})
    assert f"Sessions analysed: {total - 1} of {total}" in text
    assert "excluded from confirmatory analysis: 1" in text
    # The timeline example must start from an analysed session, not the pilot.
    assert "dataset.analysis_rows[0]" in text
    assert 'dataset.rows[0]["sessionId"]' not in text
