"""P1-3 CI hygiene: the worked example regenerates byte-identically.

``docs/examples/pilot-2026/`` commits the *curated* artifacts of the worked
example — protocol, ethics package, dry-run report, starter notebook, data
dictionary — but they are generated output, so they must never drift from
what the pipeline actually produces. This test re-runs the pipeline
hermetically (boot protocol + deterministic seeded dry run, all in-process)
and diffs the notebook and data dictionary against the committed files byte
for byte.

It is a regression guard, not a fixture: any change that makes the committed
snapshot unreproducible (a protocol edit, a column-order change, a cell-id
change) fails here until the example is regenerated with the documented
commands. The per-recipe figures/CSVs are deliberately not committed — they
regenerate with the simulate command.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "docs" / "examples" / "pilot-2026"
PROTOCOL = REPO_ROOT / "protocol" / "examples" / "pilot-study.yaml"

#: The exact invocation the worked example documents: 10 participants,
#: mixed profile, seed 42.
COUNT = 10
SEED = 42


def _regenerate(tmp_path: Path) -> tuple[str, str]:
    """Boot the middleware with the pilot protocol and dry-run it, exactly
    like `python -m middleware simulate` — returns (notebook, dictionary)."""
    from analysis.dataset import Dataset
    from analysis.notebook import build_notebook, data_dictionary_markdown
    from middleware.app import create_app
    from middleware.settings import Settings
    from protocol.loader import load_protocol

    settings = Settings(
        db_path=tmp_path / "test.sqlite3",
        data_dir=tmp_path / "data",
        port=8000,
        spa_dist=tmp_path / "no-dist",
        protocol_path=PROTOCOL,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.post(
            "/studies/pilot-2026/simulate",
            json={"count": COUNT, "profile": "mixed", "seed": SEED},
        )
        assert r.status_code == 200, r.text
        r = client.get("/studies/pilot-2026/dataset?format=json")
        assert r.status_code == 200, r.text
        ds_path = tmp_path / "dataset.json"
        ds_path.write_text(json.dumps(r.json()))
        dataset = Dataset.from_json(ds_path)

    protocol = load_protocol(PROTOCOL)
    study_id = "pilot-2026"
    notebook = json.dumps(build_notebook(protocol, dataset, study_id), indent=1) + "\n"
    dictionary = f"# {study_id} — data dictionary\n\n" + data_dictionary_markdown(
        dataset
    )
    return notebook, dictionary


def test_worked_example_artifacts_regenerate_byte_identical(tmp_path):
    notebook, dictionary = _regenerate(tmp_path)
    assert (EXAMPLE / "notebook.ipynb").read_text() == notebook, (
        "docs/examples/pilot-2026/notebook.ipynb drifted from the pipeline. "
        "Regenerate it: python -m analysis.cli notebook protocol/examples/"
        "pilot-study.yaml --server <url> --out docs/examples"
    )
    assert (EXAMPLE / "data-dictionary.md").read_text() == dictionary, (
        "docs/examples/pilot-2026/data-dictionary.md drifted from the "
        "pipeline. Regenerate it with the notebook command above."
    )
