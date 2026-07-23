"""Runtime template composition (FR-TPL): merging templates into one novel
protocol, and deriving a paper-specialised template from an archetype."""

import pytest
from protocol.loader import validate_protocol

from middleware import template_registry as tr


def test_merge_two_templates_yields_valid_protocol_with_renumbered_rqs():
    result = tr.merge_templates(["metr-rct-v1", "survey-self-report-v1"], {})
    proto = result["protocol"]

    # The merged protocol is genuinely valid — not just assembled.
    assert validate_protocol(proto) == []

    # RQs from both templates, renumbered sequentially so ids can't collide.
    ids = [rq["id"] for rq in proto["researchQuestions"]]
    assert ids == [f"RQ-{i}" for i in range(1, len(ids) + 1)]
    assert len(ids) >= 4  # metr's 3 + survey's 1

    # Every RQ is still covered by an analysis-plan entry (traceability holds).
    covered = {e["rq"] for e in proto["analysisPlan"]}
    assert set(ids) <= covered

    # Provenance: every contributing template and its papers are reported.
    contributed = {s["templateId"] for s in result["sources"]}
    assert contributed == {"metr-rct-v1", "survey-self-report-v1"}
    all_papers = {p for s in result["sources"] for p in s["papers"]}
    assert "corpus:ai-assistants-in-practice" in all_papers


def test_merge_remaps_literature_justifies_to_new_rq_ids():
    # A borrowed template's literature must point at the RENUMBERED rq ids,
    # never a stale id from before the merge.
    proto = tr.merge_templates(["metr-rct-v1", "survey-self-report-v1"], {})["protocol"]
    valid_ids = {rq["id"] for rq in proto["researchQuestions"]}
    for lit in proto["literature"]:
        for rq_id in lit.get("justifies", []):
            assert rq_id in valid_ids


def test_merge_needs_at_least_two():
    with pytest.raises(tr.TemplateError):
        tr.merge_templates(["metr-rct-v1"], {})


def test_derive_from_paper_leads_provenance_and_stays_valid():
    t = tr.derive_template_from_paper(
        "corpus:grounded-copilot", "metr-rct-v1", title="Grounded Copilot"
    )
    # The paper leads the source list — it's the design's primary citation.
    assert t["source"][0]["paperRef"] == "corpus:grounded-copilot"
    # Distinct id, and it still instantiates to a valid protocol zero-edit.
    assert t["templateId"] != "metr-rct-v1"
    vals = tr.resolve_parameters(t, {})
    proto = tr._fill(t["protocolSkeleton"], vals)
    assert validate_protocol(proto) == []
