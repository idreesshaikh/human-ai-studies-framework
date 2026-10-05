"""
Ingest-to-analysis coverage for the debrief (issue #67).

Posts real `end_survey_response` events through the HTTP `/ingest/events` boundary,
exports the study dataset, and runs the tlx-debrief recipe on it: the end-to-end proof
that a debrief response survives ingest and reaches the analysis with its six subscales
intact and timing/comments excluded.
"""

from __future__ import annotations

from pathlib import Path

import analysis.recipes  # noqa: F401 - register recipes
import pytest
from analysis.core import REGISTRY
from analysis.dataset import Dataset
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = REPO_ROOT / "protocol" / "examples" / "pilot-study.yaml"

# The exact six items the extension's end survey emits (extension/src/core/surveys.ts).
_SUBSCALES = (
    "mental_demand",
    "effort",
    "frustration",
    "time_pressure",
    "perceived_performance",
    "comprehension",
)


def _responses(seed: int) -> dict:
    return {k: 1 + (seed + i) % 7 for i, k in enumerate(_SUBSCALES)}


def _event(session: str, participant: str, condition: str, responses: dict) -> dict:
    return {
        "sessionId": session,
        "participantId": participant,
        "condition": condition,
        "ts": "2026-07-11T10:57:00.000Z",
        "seq": 0,
        "v": 4,
        "type": "end_survey_response",
        "payload": {"responses": responses, "comments": "ok", "msToComplete": 45000},
    }


@pytest.mark.parametrize("include_ai_reliance", [False, True])
def test_debrief_survives_ingest_and_drives_tlx_analysis(tmp_path, include_ai_reliance):
    settings = Settings(
        db_path=tmp_path / "t.sqlite3",
        data_dir=tmp_path / "data",
        port=8000,
        spa_dist=tmp_path / "no-dist",
        protocol_path=PROTOCOL,
    )
    batch = {
        "source": "cognitive-overlay",
        "events": [
            _event("S1", "P01", "ai-assisted", _responses(1)),
            _event("S2", "P02", "unassisted", _responses(2)),
            _event("S3", "P03", "ai-assisted", _responses(3)),
            _event("S4", "P04", "unassisted", _responses(4)),
        ],
    }
    if include_ai_reliance:
        for event in batch["events"]:
            if event["condition"] == "ai-assisted":
                event["payload"]["responses"]["ai_reliance"] = 6
    with TestClient(create_app(settings)) as client:
        r = client.post("/ingest/events", json=batch)
        assert r.status_code == 200, r.text
        assert r.json()["inserted"] == len(batch["events"]), r.json()
        doc = client.get("/studies/pilot-2026/dataset?format=json").json()

    rows = doc["rows"]
    debrief = [r for r in rows if r["type"] == "end_survey_response"]
    assert debrief, "end_survey_response events did not reach the dataset via ingest"
    assert "responses" in debrief[0]["payload"], "debrief payload lost its nesting"

    dataset = Dataset(rows=rows, study_id="pilot-2026")
    result = REGISTRY["tlx-debrief"].run(dataset)
    subscales = set(result.tables["per_condition"]["subscale"])

    expected = set(_SUBSCALES) | ({"ai_reliance"} if include_ai_reliance else set())
    assert subscales == expected
    if include_ai_reliance:
        exported = result.tables["responses"]
        assert (
            exported.loc[exported["condition"] == "unassisted", "ai_reliance"]
            .isna()
            .all()
        )
        assert (
            exported.loc[exported["condition"] == "ai-assisted", "ai_reliance"]
            .eq(6)
            .all()
        )
        assert "ai_reliance" not in set(result.tables["tests"]["subscale"])
        assert "nan" not in result.summary.lower()
    assert "msToComplete" not in subscales and "comments" not in subscales
    assert "responded" in result.summary
