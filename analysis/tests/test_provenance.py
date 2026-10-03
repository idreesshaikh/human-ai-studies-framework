"""
Provenance: whether a dataset's rows came from participants or from a dry run.

Every artefact `analysis run` writes must say which, because a reader who cannot
tell synthetic output from a finding has been handed a false result.
"""

import json
import pathlib

import analysis.recipes  # noqa: F401
import yaml
from analysis.cli import main
from analysis.dataset import Dataset
from analysis.figures import new_axes, watermark_synthetic
from analysis.runner import run_plan
from tests_support import synthetic_rows

PILOT = (
    pathlib.Path(__file__).resolve().parents[2]
    / "protocol"
    / "examples"
    / "pilot-study.yaml"
)


def _row(session: str, *, synthetic: bool | None = None) -> dict:
    row = {
        "source": "tern",
        "ts": "2026-07-11T10:00:00.000Z",
        "sessionId": session,
        "participantId": session,
        "condition": "ai-assisted",
        "type": "session_start",
        "seq": 0,
        "flags": [],
        "payload": {},
    }
    if synthetic is not None:
        row["synthetic"] = synthetic
    return row


def test_rows_without_a_synthetic_flag_are_participant_data():
    provenance = Dataset(rows=[_row("S1"), _row("S2")]).provenance

    assert provenance.kind == "participant"
    assert provenance.synthetic == 0
    assert provenance.total == 2


def test_rows_flagged_synthetic_are_reported_as_synthetic():
    provenance = Dataset(
        rows=[_row("S1", synthetic=True), _row("S2", synthetic=True)]
    ).provenance

    assert provenance.kind == "synthetic"
    assert provenance.synthetic == 2


def test_a_false_synthetic_flag_still_counts_as_participant_data():
    provenance = Dataset(rows=[_row("S1", synthetic=False)]).provenance

    assert provenance.kind == "participant"
    assert provenance.synthetic == 0


def test_participant_and_synthetic_rows_together_are_mixed():
    provenance = Dataset(rows=[_row("S1"), _row("S2", synthetic=True)]).provenance

    assert provenance.kind == "mixed"
    assert provenance.synthetic == 1
    assert provenance.participant == 1


def test_an_empty_dataset_has_no_provenance_to_report():
    assert Dataset(rows=[]).provenance.kind == "empty"


# --- Banners on written artefacts -------------------------------------------

PROTOCOL = {
    "study": {"id": "rehearsal"},
    "researchQuestions": [{"id": "RQ-P1", "text": "Does AI assistance change load?"}],
    "analysisPlan": [{"rq": "RQ-P1", "recipes": ["fatigue-by-condition"]}],
}


def _run(tmp_path, *, synthetic: bool):
    rows = [dict(r, synthetic=True) if synthetic else dict(r) for r in synthetic_rows()]
    outcome = run_plan(
        PROTOCOL,
        Dataset(rows=rows, study_id="rehearsal"),
        "rehearsal",
        out_root=tmp_path,
    )
    return outcome.out_dir


def test_report_on_synthetic_data_is_bannered_as_not_a_finding(tmp_path):
    report = (_run(tmp_path, synthetic=True) / "report.md").read_text()

    assert "SYNTHETIC DATA" in report
    assert "not a research finding" in report


def test_recipe_summary_on_synthetic_data_carries_the_same_banner(tmp_path):
    summary = (
        _run(tmp_path, synthetic=True) / "fatigue-by-condition" / "summary.md"
    ).read_text()

    assert "SYNTHETIC DATA" in summary


def test_report_on_participant_data_carries_no_synthetic_banner(tmp_path):
    report = (_run(tmp_path, synthetic=False) / "report.md").read_text()

    assert "SYNTHETIC" not in report


# --- Watermarks on figures ---------------------------------------------------


def test_watermark_stamps_the_figure_with_the_provenance_kind():
    fig, _ = new_axes("t", "x", "y")

    watermark_synthetic(fig, "synthetic")

    assert any("SYNTHETIC" in t.get_text() for t in fig.texts)


def test_participant_figures_are_never_watermarked():
    fig, _ = new_axes("t", "x", "y")

    watermark_synthetic(fig, "participant")

    assert fig.texts == []


def test_figures_written_from_a_synthetic_run_differ_from_participant_ones(tmp_path):
    synthetic = _run(tmp_path / "s", synthetic=True)
    participant = _run(tmp_path / "p", synthetic=False)
    name = "fatigue-by-condition/by_condition.png"

    assert (synthetic / name).read_bytes() != (participant / name).read_bytes()


# --- The CLI refuses to pass mixed provenance off as a result ----------------


def _write_inputs(tmp_path, rows):
    """
    The real pilot protocol, with its plan trimmed to the one recipe these fixture
    rows satisfy - so the exit code under test is the provenance verdict and not a
    plan-validation failure.
    """
    doc = yaml.safe_load(PILOT.read_text())
    doc["analysisPlan"] = [{"rq": "RQ-P1", "recipes": ["fatigue-by-condition"]}]
    protocol = tmp_path / "study.yaml"
    protocol.write_text(yaml.safe_dump(doc, sort_keys=False))
    (tmp_path / "data.json").write_text(json.dumps({"studyId": "pilot", "rows": rows}))
    return [
        "run",
        str(protocol),
        "--dataset",
        str(tmp_path / "data.json"),
        "--out",
        str(tmp_path / "out"),
    ]


def test_run_exits_non_zero_when_the_dataset_mixes_synthetic_and_real_rows(tmp_path):
    rows = synthetic_rows()
    mixed = [dict(r, synthetic=(i % 2 == 0)) for i, r in enumerate(rows)]

    assert main(_write_inputs(tmp_path, mixed)) == 3


def test_run_accepts_mixed_provenance_when_explicitly_allowed(tmp_path):
    rows = synthetic_rows()
    mixed = [dict(r, synthetic=(i % 2 == 0)) for i, r in enumerate(rows)]

    assert main([*_write_inputs(tmp_path, mixed), "--allow-mixed-provenance"]) == 0


def test_a_wholly_synthetic_run_is_bannered_but_still_succeeds(tmp_path):
    rows = [dict(r, synthetic=True) for r in synthetic_rows()]

    assert main(_write_inputs(tmp_path, rows)) == 0


def test_notebook_fetches_dry_run_rows_only_when_requested(tmp_path, monkeypatch):
    fetched = []

    def fetch(cls, server, study_id, *, include_synthetic=False):
        fetched.append((server, study_id, include_synthetic))
        return Dataset(synthetic_rows(), study_id=study_id)

    monkeypatch.setattr(Dataset, "fetch", classmethod(fetch))

    assert (
        main(
            [
                "notebook",
                str(PILOT),
                "--server",
                "http://example.test",
                "--include-synthetic",
                "--out",
                str(tmp_path),
            ]
        )
        == 0
    )
    assert fetched == [("http://example.test", "pilot-2026", True)]
