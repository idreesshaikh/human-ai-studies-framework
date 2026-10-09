import copy
from pathlib import Path

import pytest
import yaml
from middleware.db import ProtocolDraftRow, make_session_factory
from protocol.loader import load_protocol
from test_power_route import bearer, make_study
from test_power_route import client as power_client  # noqa: F401 - pytest fixture alias

ROOT = Path(__file__).parents[2]


@pytest.fixture
def client(request):
    return request.getfixturevalue("power_client")


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("get", "plan", None),
        (
            "post",
            "plan",
            {
                "design": "within-subjects",
                "test": "wilcoxon",
                "measure_id": "completion-time",
            },
        ),
        ("post", "pilot-variance", {}),
        ("get", "control-arm-audit", None),
        ("post", "sessions/private/annotation", {"pilot": True, "reason": "test"}),
        (
            "post",
            "audit-calibration",
            {"labels": {"private": True}, "source": "independent test fixture"},
        ),
        ("get", "lineage", None),
        ("get", "design-card", None),
    ],
)
def test_planner_routes_require_study_membership(client, method, path, body):
    study = make_study(client, "alice")
    request = getattr(client, method)
    kwargs = {"json": body} if body is not None else {}
    url = f"/studies/{study}/{path}"
    assert request(url, **kwargs).status_code == 401
    assert request(url, headers=bearer("bob"), **kwargs).status_code == 403


def test_rerun_comparison_authorizes_both_studies(client):
    original = make_study(client, "bob")
    rerun = make_study(client, "alice")
    # Both designs are private; reading a re-run must not leak the original.
    doc = load_protocol(ROOT / "protocol/examples/planner-v6.yaml")
    doc["study"]["id"] = original
    newer = copy.deepcopy(doc)
    newer["study"]["id"] = rerun
    newer["rerunOf"] = original
    # Access the isolated test database directly to record both protocols.
    with make_session_factory(f"sqlite:///{client.db_path}")() as s:
        for study, protocol in ((original, doc), (rerun, newer)):
            s.add(
                ProtocolDraftRow(
                    study_id=study,
                    yaml=yaml.safe_dump(protocol),
                    compilation_id="",
                    updated_at="",
                )
            )
        s.commit()
    assert (
        client.get(f"/studies/{rerun}/lineage", headers=bearer("alice")).status_code
        == 403
    )
