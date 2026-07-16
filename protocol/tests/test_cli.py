import json

from protocol.cli import main


def test_validate_example_ok(example_path, capsys):
    assert main(["validate", str(example_path)]) == 0
    out = capsys.readouterr().out
    assert "OK" in out
    assert "All research questions are covered" in out


def test_validate_broken_fixture_fails_naming_field(fixtures_dir, capsys):
    exit_code = main(
        ["validate", str(fixtures_dir / "broken-missing-conditions.yaml")]
    )
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "conditions" in err
    assert "participants.design" in err


def test_status_reports_phase_and_missing_gates(example_path, capsys):
    assert main(["status", str(example_path)]) == 0
    out = capsys.readouterr().out
    assert "Current phase: design" in out
    assert "ethics-approval.pdf" in out


def test_status_with_artifact_flags_advances_phase(example_path, capsys):
    assert (
        main(
            [
                "status",
                str(example_path),
                "--artifact",
                "protocol-validated.txt",
                "--artifact",
                "task-definitions.md",
            ]
        )
        == 0
    )
    assert "Current phase: ethics" in capsys.readouterr().out


def test_status_with_artifacts_dir(example_path, tmp_path, capsys):
    for name in ("protocol-validated.txt", "task-definitions.md"):
        (tmp_path / name).write_text("present", "utf-8")
    assert main(["status", str(example_path), "--artifacts-dir", str(tmp_path)]) == 0
    assert "Current phase: ethics" in capsys.readouterr().out


def test_derive_emits_pasteable_settings_json(example_path, capsys):
    assert (
        main(
            [
                "derive",
                "overlay-settings",
                str(example_path),
                "--participant",
                "P01",
                "--condition",
                "ai-assisted",
            ]
        )
        == 0
    )
    settings = json.loads(capsys.readouterr().out)
    assert settings["cognitiveOverlay.participantId"] == "P01"
    assert all(key.startswith("cognitiveOverlay.") for key in settings)


def test_derive_unknown_condition_fails(example_path, capsys):
    exit_code = main(
        [
            "derive",
            "overlay-settings",
            str(example_path),
            "--participant",
            "P01",
            "--condition",
            "with-ai",
        ]
    )
    assert exit_code == 1
    assert "not declared" in capsys.readouterr().err
