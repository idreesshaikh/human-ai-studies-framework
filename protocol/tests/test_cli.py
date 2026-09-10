import json

from protocol.cli import main


def test_validate_example_ok(example_path, capsys):
    assert main(["validate", str(example_path)]) == 0
    out = capsys.readouterr().out
    assert "OK" in out
    assert "All research questions are covered" in out


def test_validate_broken_fixture_fails_naming_field(fixtures_dir, capsys):
    exit_code = main(["validate", str(fixtures_dir / "broken-missing-conditions.yaml")])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "conditions" in err
    assert "participants.design" in err


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
    assert settings["tern.participantId"] == "P01"
    assert all(key.startswith("tern.") for key in settings)


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
