"""Featured starters produce v6 protocols and executable, design-matched analyses."""

import json
from pathlib import Path

import analysis.recipes  # noqa: F401 - registers recipes
import pytest
import yaml
from analysis.core import REGISTRY
from analysis.dataset import Dataset
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings
from protocol.loader import load_protocol
from protocol.versioning import version_record

from middleware import template_registry

ROOT = Path(__file__).resolve().parents[2]
IDS = ["within-subjects-crossover-v2", "two-group-rct-v2", "metr-inspired-v1"]


@pytest.mark.parametrize("template_id", IDS)
def test_featured_template_reaches_a_recorded_plan(tmp_path, template_id):
    assert template_id in json.loads((ROOT / "templates/featured.json").read_text())
    protocol = template_registry.instantiate_template(template_id, {})["protocol"]
    assert protocol["literature"][0]["paperRef"].startswith("arxiv:")
    assert any(
        word in protocol["session"]["taskDescription"]
        for word in ("adaptation", "externally")
    )
    path = tmp_path / "protocol.yaml"
    path.write_text(yaml.safe_dump(protocol))
    assert load_protocol(path)["protocolVersion"] == 6
    settings = Settings(
        db_path=tmp_path / "templates.sqlite3",
        data_dir=tmp_path / "data",
        spa_dist=tmp_path / "no-dist",
        auth="none",
    )
    with TestClient(create_app(settings)) as client:
        study = client.post(
            "/projects/implicit/studies",
            json={"name": template_id, "protocol": protocol},
        )
        assert study.status_code == 200, study.text
        sid = study.json()["id"]
        plan = client.post(
            f"/studies/{sid}/plan",
            json={
                "effect": 0.5,
                "design": protocol["participants"]["design"],
                "counterbalanced": protocol["participants"]["counterbalanced"],
                "measure_id": "first-green-time",
                "test": "paired-t"
                if protocol["participants"]["design"] == "within-subjects"
                else "two-sample-t",
            },
        )
        assert plan.status_code == 200, plan.text
        assert plan.json()["required"]["totalN"] > 0


@pytest.mark.parametrize("template_id", IDS)
def test_featured_recipes_run_on_design_matched_synthetic_rows(template_id):
    protocol = template_registry.instantiate_template(template_id, {})["protocol"]
    paired = protocol["participants"]["design"] == "within-subjects"
    rows = []
    for arm, condition in enumerate(protocol["conditions"]):
        for i in range(6):
            pid = f"P{i}" if paired else f"P{arm}-{i}"
            base = {
                "sessionId": f"{condition}-{pid}",
                "participantId": pid,
                "condition": condition,
                "ts": "2026-10-08T12:00:00Z",
                "flags": [],
                "source": "tern",
            }
            rows.append(
                {
                    **base,
                    "seq": 1,
                    "type": "task_outcome",
                    "payload": {
                        "firstGreenMs": 1000 + i * 130 + arm * (400 + i * 17),
                        "passed": True,
                    },
                }
            )
            for survey in protocol["instruments"]["surveys"]:
                responses = {
                    item["id"]: 20 + i * 3 + arm * 10 for item in survey["items"]
                }
                rows.append(
                    {
                        **base,
                        "seq": 2,
                        "type": "survey_response",
                        "payload": {
                            "instrumentId": survey["id"],
                            "instrumentVersion": survey["version"],
                            "instrumentHash": version_record(survey)["sha256"],
                            "responses": responses,
                        },
                    }
                )
    dataset = Dataset(rows, meta={"protocol": protocol})
    for entry in protocol["analysisPlan"]:
        for recipe_id in entry["recipes"]:
            assert recipe_id in REGISTRY
            result = REGISTRY[recipe_id].run(dataset)
            assert result.tables, (template_id, recipe_id, result.summary)
            assert not result.tables["tests"].empty, (
                template_id,
                recipe_id,
                result.summary,
            )


def test_featured_route_skips_unknown_ids_with_a_warning(tmp_path, monkeypatch, caplog):
    featured = tmp_path / "featured.json"
    featured.write_text(json.dumps([*IDS, "missing-template"]))
    monkeypatch.setattr(template_registry, "FEATURED_FILE", featured)
    settings = Settings(
        db_path=tmp_path / "featured.sqlite3",
        data_dir=tmp_path / "data",
        spa_dist=tmp_path / "no-dist",
        auth="none",
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/templates/featured")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == IDS
    assert "missing-template" in caplog.text
