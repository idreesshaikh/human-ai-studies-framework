"""No registry template still promises the ethics gate that was removed.

Found by actually generating an ethics package end to end: every template's
``ethicsRef`` default read "gate blocks data-collection" - a mechanism that
does not exist any more (the lifecycle board and its ethics gate were
removed; approval is the researcher's own to obtain and record). Left alone,
that sentence would have gone out in a real ethics submission.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "templates" / "registry"

#: Language that names a mechanism the platform no longer has. A new match
#: here means a template (or a doc that copied from one) is describing
#: something that isn't true any more.
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
