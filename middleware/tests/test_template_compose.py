"""
Runtime template composition (FR-TPL): merging templates into one novel protocol.
"""

import pytest
from protocol.loader import validate_protocol

from middleware import template_registry as tr


def test_merge_two_templates_yields_valid_protocol_with_renumbered_rqs():
    result = tr.merge_templates(["metr-rct-v1", "survey-self-report-v1"], {})
    proto = result["protocol"]

    assert validate_protocol(proto) == []

    # RQs from both templates, renumbered sequentially so ids can't collide.
    ids = [rq["id"] for rq in proto["researchQuestions"]]
    assert ids == [f"RQ-{i}" for i in range(1, len(ids) + 1)]
    assert len(ids) >= 4

    covered = {e["rq"] for e in proto["analysisPlan"]}
    assert set(ids) <= covered

    contributed = {s["templateId"] for s in result["sources"]}
    assert contributed == {"metr-rct-v1", "survey-self-report-v1"}
    all_papers = {p for s in result["sources"] for p in s["papers"]}
    assert "corpus:ai-assistants-in-practice" in all_papers


def test_merge_remaps_literature_justifies_to_new_rq_ids():
    # A borrowed template's literature must point at the RENUMBERED rq ids, never a
    # stale id from before the merge.
    proto = tr.merge_templates(["metr-rct-v1", "survey-self-report-v1"], {})["protocol"]
    valid_ids = {rq["id"] for rq in proto["researchQuestions"]}
    for lit in proto["literature"]:
        for rq_id in lit.get("justifies", []):
            assert rq_id in valid_ids


def test_merge_needs_at_least_two():
    with pytest.raises(tr.TemplateError):
        tr.merge_templates(["metr-rct-v1"], {})
