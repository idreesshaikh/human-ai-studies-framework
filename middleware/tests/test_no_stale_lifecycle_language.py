"""No registry template still promises the ethics gate that was removed."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "templates" / "registry"

STALE_PHRASES = ("gate blocks", "lifecycle gate", "ethics gate")


def test_no_registry_template_mentions_the_removed_ethics_gate():
    offenders = []
    for path in sorted(REGISTRY.glob("*.yaml")):
        text = path.read_text().lower()
        if any(phrase in text for phrase in STALE_PHRASES):
            offenders.append(path.name)
    assert offenders == []


def test_example_protocols_carry_no_stale_gate_language():
    examples_dir = REPO_ROOT / "protocol" / "examples"
    offenders = []
    for path in sorted(examples_dir.glob("*.yaml")):
        text = path.read_text().lower()
        if any(phrase in text for phrase in STALE_PHRASES):
            offenders.append(path.name)
    assert offenders == []
