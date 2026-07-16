import pytest
from protocol.errors import ProtocolError
from protocol.loader import load_protocol, uncovered_rqs


def test_pilot_example_validates(pilot):
    assert pilot["protocolVersion"] == 1
    assert pilot["conditions"] == ["ai-assisted", "unassisted"]


def test_missing_file_is_a_protocol_error(tmp_path):
    with pytest.raises(ProtocolError, match="cannot read"):
        load_protocol(tmp_path / "nope.yaml")


def test_invalid_yaml_syntax(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("study: [unclosed", "utf-8")
    with pytest.raises(ProtocolError, match="invalid YAML"):
        load_protocol(bad)


def test_non_mapping_document(tmp_path):
    bad = tmp_path / "list.yaml"
    bad.write_text("- just\n- a\n- list\n", "utf-8")
    with pytest.raises(ProtocolError, match="mapping"):
        load_protocol(bad)


def test_broken_fixture_names_offending_fields(fixtures_dir):
    with pytest.raises(ProtocolError) as exc:
        load_protocol(fixtures_dir / "broken-missing-conditions.yaml")
    message = str(exc.value)
    assert "conditions" in message
    assert "participants.planned" in message
    assert "participants.design" in message


def test_unknown_rq_reference_is_rejected(fixtures_dir):
    with pytest.raises(ProtocolError, match=r"analysisPlan.*RQ-X2"):
        load_protocol(fixtures_dir / "broken-unknown-rq.yaml")


def test_duplicate_phase_is_rejected(pilot_doc, write_protocol):
    pilot_doc["phases"].append({"name": "design", "gates": []})
    with pytest.raises(ProtocolError, match="more than once"):
        load_protocol(write_protocol(pilot_doc))


def test_unknown_top_level_key_is_rejected(pilot_doc, write_protocol):
    pilot_doc["surprise"] = True
    with pytest.raises(ProtocolError, match="surprise"):
        load_protocol(write_protocol(pilot_doc))


def test_pilot_covers_every_rq(pilot):
    assert uncovered_rqs(pilot) == []


def test_uncovered_rq_is_reported(pilot_doc, write_protocol):
    dropped = pilot_doc["analysisPlan"].pop()
    protocol = load_protocol(write_protocol(pilot_doc))
    assert uncovered_rqs(protocol) == [dropped["rq"]]
