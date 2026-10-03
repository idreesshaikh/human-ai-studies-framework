"""
Ingest-to-analysis coverage for the debrief (issue #67).

Unlike the analysis-layer regression in analysis/tests/test_tlx_debrief.py, this
drives the *real* path: the middleware generates and ingests debrief events
(`end_survey_response`, nested payload) via the simulate route, the dataset export
returns them, and the tlx-debrief recipe runs on that exported dataset. It is the
end-to-end proof that a debrief response survives ingest and reaches the analysis
with its subscales intact and timing/comments excluded.
"""

from __future__ import annotations

from pathlib import Path

import analysis.recipes  # noqa: F401 - register recipes
from analysis.core import REGISTRY
from analysis.dataset import Dataset
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = REPO_ROOT / "protocol" / "examples" / "pilot-study.yaml"

# The TLX items the extension can emit (extension/src/core/surveys.ts); nothing else
# in a debrief payload is a rating.
_VALID_SUBSCALES = {
    "mental_demand",
    "effort",
    "frustration",
    "time_pressure",
    "perceived_performance",
    "comprehension",
    "ai_reliance",
}


def test_debrief_survives_ingest_and_drives_tlx_analysis(tmp_path):
    settings = Settings(
        db_path=tmp_path / "t.sqlite3",
        data_dir=tmp_path / "data",
        port=8000,
        spa_dist=tmp_path / "no-dist",
        protocol_path=PROTOCOL,
    )
    with TestClient(create_app(settings)) as client:
        r = client.post(
            "/studies/pilot-2026/simulate",
            json={"count": 4, "profile": "mixed", "seed": 7},
        )
        assert r.status_code == 200, r.text
        # The debrief event reaches the store under the real v4 name.
        doc = client.get(
            "/studies/pilot-2026/dataset?format=json&includeSynthetic=true"
        ).json()

    rows = doc["rows"]
    debrief = [r for r in rows if r["type"] == "end_survey_response"]
    assert debrief, "no end_survey_response events survived ingest"
    assert "responses" in debrief[0]["payload"], "debrief payload lost its nesting"

    dataset = Dataset(rows=rows, study_id="pilot-2026")
    result = REGISTRY["tlx-debrief"].run(dataset)
    subscales = set(result.tables["per_condition"]["subscale"])

    assert subscales, "tlx-debrief produced no subscales from ingested data"
    assert subscales <= _VALID_SUBSCALES, f"unexpected subscale(s): {subscales}"
    assert "msToComplete" not in subscales and "comments" not in subscales
    assert "responded" in result.summary
