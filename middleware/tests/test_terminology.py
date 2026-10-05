"""Visible terminology is consistent while historical wire identities remain valid."""

from pathlib import Path

import yaml
from middleware.app import canonical_source
from protocol.loader import load_schema

ROOT = Path(__file__).resolve().parents[2]


def test_template_designs_use_protocol_names_without_renaming_ids():
    allowed = set(
        load_schema()["properties"]["participants"]["properties"]["design"]["enum"]
    )
    paths = sorted((ROOT / "templates/registry").glob("*.yaml"))
    assert paths
    for path in paths:
        template = yaml.safe_load(path.read_text())
        assert template["templateId"] == path.stem
        assert template["protocolSkeleton"]["participants"]["design"] in allowed


def test_historical_editor_source_maps_to_tern():
    assert canonical_source("cognitive-overlay") == "tern"
    assert canonical_source("tern") == "tern"


def test_enrollment_actions_do_not_claim_real_participation():
    source = (
        ROOT / "platform/src/components/enrollment/EnrollmentPanel.tsx"
    ).read_text()
    dialog = (ROOT / "platform/src/components/enrollment/MintDialog.tsx").read_text()
    assert "Create participant links" in dialog
    assert "enrollment link" in source
    assert "Create " in dialog
    assert "Mint participant" not in source + dialog
