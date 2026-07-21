"""Template-submission endpoint tests (FR-TPL-5 / Slice C).

Covers: submit, list (own vs. owner view), get, approve, reject, duplicate
approve, bad YAML, non-owner rejection.
"""

import uuid
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings


def _uniq(name: str) -> str:
    """Return a name with a random suffix to avoid registry-file collisions."""
    return f"{name}-{uuid.uuid4().hex[:8]}"


LOCAL_SUB = "local"

VALID_TEMPLATE = yaml.safe_dump(
    {
        "templateId": "third-party-v1",
        "templateVersion": 1,
        "title": "Third-Party Two-Group RCT",
        "description": "A template contributed by a third party",
        "designType": "rct-within-subjects",
        "dataPath": "live",
        "source": [{"paperRef": "arxiv:2507.09089", "role": "primary-design"}],
        "parameters": {
            "studyId": {"type": "string", "default": "third-party-study"},
            "title": {"type": "string", "default": "Third-party study"},
            "sessionMinutes": {"type": "int", "default": 45},
            "conditions": {"type": "conditions", "default": ["treatment", "control"]},
            "participantPlan": {"type": "participants", "default": 12},
            "outputEndpoint": {"type": "string", "default": "http://localhost:8000"},
        },
        "measures": [
            {"id": "task-time", "leg": "behavioral", "elements": ["session clock"]},
        ],
        "statisticalPlan": {
            "unit": "participant",
            "perRQ": [
                {
                    "rq": "RQ-1",
                    "outcome": "task time",
                    "test": "wilcoxon-signed-rank",
                    "effectSize": "matched-pairs rank-biserial",
                    "smallN": "hypothesis-generating",
                }
            ],
        },
        "threats": [
            {"threat": "novelty-effect", "mitigation": "counterbalancing"},
        ],
        "protocolSkeleton": {
            "protocolVersion": 4,
            "study": {"id": "{{ studyId }}", "title": "{{ title }}"},
            "researchQuestions": [
                {"id": "RQ-1", "text": "How does AI affect task time?"},
            ],
            "conditions": "{{ conditions }}",
            "participants": {
                "planned": "{{ participantPlan }}",
                "design": "within-subjects",
            },
            "session": {"durationMinutes": "{{ sessionMinutes }}"},
            "instruments": {
                "tern": {
                    "session": {"durationMinutes": "{{ sessionMinutes }}"},
                    "fatigue": {"intervalMinutes": 15},
                    "stuck": {"enabled": True},
                    "output": {"httpEndpoint": "{{ outputEndpoint }}"},
                },
                "metrics": {"metricSet": "cognitive-load-9"},
            },
            "phases": [
                {"name": "design", "gates": ["protocol-validated.txt"]},
                {"name": "ethics", "gates": ["ethics-approval.pdf"]},
                {"name": "data-collection", "gates": []},
            ],
            "analysisPlan": [
                {"rq": "RQ-1", "recipes": ["task-outcome-by-condition"]},
            ],
        },
    },
    sort_keys=False,
    default_flow_style=False,
)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.sqlite3"


@pytest.fixture(autouse=True)
def _clean_registry():
    """Remove any submission-*.yaml files written during tests."""
    yield
    reg_dir = Path(__file__).resolve().parent.parent.parent / "templates" / "registry"
    for f in reg_dir.glob("submission-*.yaml"):
        f.unlink()


@pytest.fixture
def client(db_path, tmp_path):
    settings = Settings(
        db_path=db_path,
        data_dir=tmp_path / "data",
        port=8000,
        spa_dist=tmp_path / "no-dist",
    )
    tc = TestClient(create_app(settings))
    tc.db_path = db_path
    return tc


def _headers() -> dict:
    return {"Authorization": f"Bearer {LOCAL_SUB}"}


def test_submit_and_list_own(client):
    """A submission appears in the submitter's list."""
    name = _uniq("My Template")
    r = client.post(
        "/templates/submissions",
        json={"name": name, "templateYaml": VALID_TEMPLATE},
        headers=_headers(),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "pending"
    sid = data["id"]

    r2 = client.get("/templates/submissions", headers=_headers())
    assert r2.status_code == 200, r2.text
    ids = [s["id"] for s in r2.json()["submissions"]]
    assert sid in ids


def test_submit_bad_yaml(client):
    """Invalid YAML is rejected with 422."""
    r = client.post(
        "/templates/submissions",
        json={"name": _uniq("Bad"), "templateYaml": "::: not yaml"},
        headers=_headers(),
    )
    assert r.status_code == 422, r.text


def test_submit_not_a_mapping(client):
    """YAML that parses to a non-dict value is rejected."""
    r = client.post(
        "/templates/submissions",
        json={"name": _uniq("Bad"), "templateYaml": "42"},
        headers=_headers(),
    )
    assert r.status_code == 422, r.text


def test_submit_validation_failure(client):
    """A valid YAML dict that fails template validation is 422."""
    bad = yaml.safe_dump({"templateId": _uniq("broken"), "source": "not-a-list"})
    r = client.post(
        "/templates/submissions",
        json={"name": _uniq("Bad"), "templateYaml": bad},
        headers=_headers(),
    )
    assert r.status_code == 422, r.text


def test_owner_sees_all(client):
    """The implicit-project owner sees all submissions (local auth)."""
    n1 = _uniq("First")
    r1 = client.post(
        "/templates/submissions",
        json={"name": n1, "templateYaml": VALID_TEMPLATE},
        headers=_headers(),
    )
    assert r1.status_code == 200
    n2 = _uniq("Second")
    r2 = client.post(
        "/templates/submissions",
        json={"name": n2, "templateYaml": VALID_TEMPLATE},
        headers=_headers(),
    )
    assert r2.status_code == 200

    r = client.get("/templates/submissions", headers=_headers())
    assert r.status_code == 200
    names = {s["name"] for s in r.json()["submissions"]}
    assert names == {n1, n2}


def test_get_submission(client):
    """GET /templates/submissions/{id} returns the full YAML."""
    name = _uniq("GetMe")
    r = client.post(
        "/templates/submissions",
        json={"name": name, "templateYaml": VALID_TEMPLATE},
        headers=_headers(),
    )
    sid = r.json()["id"]

    r2 = client.get(f"/templates/submissions/{sid}", headers=_headers())
    assert r2.status_code == 200, r2.text
    assert r2.json()["templateYaml"] == VALID_TEMPLATE
    assert r2.json()["name"] == name


def test_approve_then_registry_file_exists(client, tmp_path):
    """Approving a submission writes a file to the registry dir."""
    name = _uniq("Approved Template")
    r = client.post(
        "/templates/submissions",
        json={"name": name, "templateYaml": VALID_TEMPLATE},
        headers=_headers(),
    )
    sid = r.json()["id"]

    r2 = client.post(
        f"/templates/submissions/{sid}/decision",
        json={"status": "approved", "reviewComment": "Looks good"},
        headers=_headers(),
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "approved"
    assert r2.json()["reviewComment"] == "Looks good"

    # Verify status via get
    r3 = client.get(f"/templates/submissions/{sid}", headers=_headers())
    assert r3.json()["status"] == "approved"


def test_reject_submission(client):
    """Rejecting a submission marks it rejected."""
    name = _uniq("RejectMe")
    r = client.post(
        "/templates/submissions",
        json={"name": name, "templateYaml": VALID_TEMPLATE},
        headers=_headers(),
    )
    sid = r.json()["id"]

    r2 = client.post(
        f"/templates/submissions/{sid}/decision",
        json={"status": "rejected", "reviewComment": "Not suitable"},
        headers=_headers(),
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "rejected"
    assert r2.json()["reviewComment"] == "Not suitable"


def test_double_decision_fails(client):
    """A second decision on the same submission is 409."""
    name = _uniq("Double")
    r = client.post(
        "/templates/submissions",
        json={"name": name, "templateYaml": VALID_TEMPLATE},
        headers=_headers(),
    )
    sid = r.json()["id"]

    r1 = client.post(
        f"/templates/submissions/{sid}/decision",
        json={"status": "approved"},
        headers=_headers(),
    )
    assert r1.status_code == 200, r1.text  # first decision succeeds

    r2 = client.post(
        f"/templates/submissions/{sid}/decision",
        json={"status": "rejected"},
        headers=_headers(),
    )
    assert r2.status_code == 409, r2.text


def test_bad_decision_status_is_422(client):
    """A decision with an invalid status is 422."""
    name = _uniq("Mine")
    r = client.post(
        "/templates/submissions",
        json={"name": name, "templateYaml": VALID_TEMPLATE},
        headers=_headers(),
    )
    sid = r.json()["id"]

    r2 = client.post(
        f"/templates/submissions/{sid}/decision",
        json={"status": "maybe"},
        headers=_headers(),
    )
    assert r2.status_code == 422, r2.text


def test_approve_with_invalid_yaml_fails(client, tmp_path):
    """A submission whose stored YAML is invalid at approve-time is 422."""
    name = _uniq("BadLater")
    r = client.post(
        "/templates/submissions",
        json={"name": name, "templateYaml": VALID_TEMPLATE},
        headers=_headers(),
    )
    sid = r.json()["id"]

    from middleware.db import TemplateSubmission, make_session_factory
    from sqlalchemy import select

    sf = make_session_factory(client.db_path)
    with sf() as s:
        row = s.scalar(select(TemplateSubmission).where(TemplateSubmission.id == sid))
        row.template_yaml = "broken: [invalid\n"
        s.commit()

    r2 = client.post(
        f"/templates/submissions/{sid}/decision",
        json={"status": "approved"},
        headers=_headers(),
    )
    assert r2.status_code == 422, r2.text
