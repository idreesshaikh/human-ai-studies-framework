"""Replication-kit tests (FR-PROT-7, NFR-6; docs/archive/roadmap/09 item 1).

The headline test IS the acceptance criterion: re-running the analysis
from the kit's own dataset regenerates a byte-identical ``report.md``
("fresh checkout + the kit" simulated as a clean output directory and the
same pinned environment). A second test proves the archive itself is
deterministic: two exports of the same inputs are byte-identical.
"""

import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest
from protocol.export import KIT_FORMAT_VERSION, build_kit

MINI_PROTOCOL = """\
protocolVersion: 1
study:
  id: kit-test
  title: "Replication-kit test study"
  researchers: [Tester]
  ethicsRef: "n/a - synthetic"
researchQuestions:
  - id: RQ-P1
    text: "Does the kit reproduce?"
conditions: [ai-assisted, unassisted]
participants:
  planned: 2
  design: within-subjects
  counterbalanced: true
session:
  durationMinutes: 45
  taskDescription: "synthetic"
instruments:
  cognitiveOverlay:
    session: {durationMinutes: 45}
    fatigue: {intervalMinutes: 15, waitForPauseSeconds: 4}
    stuck: {enabled: true, thresholdSeconds: 90}
    output: {httpEndpoint: "http://127.0.0.1:8000/ingest/events"}
phases:
  - name: design
    gates: []
analysisPlan:
  - rq: RQ-P1
    recipes: [fatigue-by-condition]
"""


def _dataset() -> dict:
    rows = []
    for i, (participant, condition, score) in enumerate([
        ("P1", "ai-assisted", 2), ("P1", "unassisted", 3),
        ("P2", "ai-assisted", 3), ("P2", "unassisted", 4),
    ]):
        for j, minute in enumerate((15, 30)):
            rows.append({
                "v": 3,
                "ts": f"2026-07-12T{9 + i:02d}:{minute:02d}:00.000Z",
                "sessionId": f"S-{participant}-{condition[:2]}",
                "participantId": participant,
                "condition": condition,
                "seq": j,
                "type": "fatigue_response",
                "source": "cognitive-overlay",
                "payload": {"score": score + j, "latencyMs": 3000},
            })
    return {"studyId": "kit-test", "rows": rows}


@pytest.fixture()
def kit(tmp_path) -> Path:
    proto = tmp_path / "protocol.yaml"
    proto.write_text(MINI_PROTOCOL)
    out = tmp_path / "kit.tar.gz"
    build_kit(proto, _dataset(), out, repo_root=Path.cwd())
    return out


def test_kit_contents_complete(kit, tmp_path):
    with tarfile.open(kit) as tar:
        names = tar.getnames()
        manifest = json.loads(
            tar.extractfile("kit-test-replication-kit/versions.json").read()
        )
    for member in (
        "README.md", "protocol.yaml", "dataset.json", "versions.json",
        "literature.json", "uv.lock", ".python-version",
        "schema/study-protocol.schema.json",
        "report/kit-test/report.md",
    ):
        assert f"kit-test-replication-kit/{member}" in names, member
    assert manifest["kitFormatVersion"] == KIT_FORMAT_VERSION
    assert manifest["studyId"] == "kit-test"
    assert manifest["eventSchemaVersions"] == [3]
    assert manifest["datasetRows"] == 8
    # The recipe registry travels with the kit (versions of the analyses).
    ids = {r["id"] for r in manifest["recipes"]}
    assert "fatigue-by-condition" in ids
    assert "ziegler-acceptance-rate" in ids


def test_reproduction_is_byte_identical(kit, tmp_path):
    """FR-PROT-7 acceptance: kit dataset -> analysis run -> same report.md."""
    extract = tmp_path / "x"
    with tarfile.open(kit) as tar:
        tar.extractall(extract, filter="data")
    root = extract / "kit-test-replication-kit"

    fresh = tmp_path / "fresh-results"
    proc = subprocess.run(
        [
            sys.executable, "-m", "analysis.cli", "run",
            str(root / "protocol.yaml"),
            "--dataset", str(root / "dataset.json"),
            "--out", str(fresh),
        ],
        capture_output=True, text=True,
        env={**os.environ, "SOURCE_DATE_EPOCH": "0"},
    )
    assert proc.returncode == 0, proc.stderr
    reproduced = (fresh / "kit-test" / "report.md").read_bytes()
    shipped = (root / "report" / "kit-test" / "report.md").read_bytes()
    assert reproduced == shipped
    # Tables too - the honest-stats lines must survive the round trip.
    assert (fresh / "kit-test" / "fatigue-by-condition" / "test.csv").read_bytes() == (
        root / "report/kit-test/fatigue-by-condition/test.csv"
    ).read_bytes()


def test_export_is_deterministic(tmp_path):
    """NFR-6: same protocol + dataset -> byte-identical archives."""
    proto = tmp_path / "protocol.yaml"
    proto.write_text(MINI_PROTOCOL)
    a = tmp_path / "a.tar.gz"
    b = tmp_path / "b.tar.gz"
    build_kit(proto, _dataset(), a, repo_root=Path.cwd())
    build_kit(proto, _dataset(), b, repo_root=Path.cwd())
    assert a.read_bytes() == b.read_bytes()
