"""Self-improvement retrospective (FR-META-2, MP-11 Part C): evidence
collection, the FR-ETH-4 prompt boundary, the offline bundle, and a scripted
Claude draft."""

from analysis import retrospective

# A findings log with the two acceptance findings (a seq gap + a
# requires-fail) plus an aggregate status carrying participant sessions the
# prompt must NOT leak (FR-ETH-4).
FINDINGS = [
    {
        "id": 1, "kind": "seq-gap", "requirementId": "FR-ING-3",
        "message": "S1 (cognitive-overlay): 1 seq gap, 1 event missing",
        "context": {"session": "S1", "source": "cognitive-overlay"},
        "status": "open",
    },
    {
        "id": 2, "kind": "requires-fail", "requirementId": "FR-ANA-2",
        "message": "agent-interaction-dynamics (RQ-P5): MISSING DATA - "
        "requires event type 'agent_turn'",
        "context": {"recipe": "agent-interaction-dynamics", "rq": "RQ-P5"},
        "status": "open",
    },
]
STATUS = {
    "lifecycle": {"currentPhase": "analysis"},
    "plannedParticipants": 6,
    "sessions": [  # carries participant/session ids the prompt must drop
        {"sessionId": "S1", "participantId": "P01", "condition": "ai-assisted"},
        {"sessionId": "S2", "participantId": "P02", "condition": "unassisted"},
    ],
    "researchQuestions": [
        {"id": "RQ-P5", "recipes": ["agent-interaction-dynamics"], "recipeRuns": []},
    ],
}


def _fake_fetch(url: str):
    if url.endswith("/findings"):
        return FINDINGS
    if url.endswith("/status"):
        return STATUS
    raise AssertionError(url)


def test_collect_evidence_pulls_findings_and_aggregate_coverage():
    ev = retrospective.collect_evidence(
        "http://mw", "pilot-2026", None, fetch=_fake_fetch
    )
    assert len(ev["findings"]) == 2
    # Coverage is aggregate only - a session *count*, not the session list.
    assert ev["coverage"]["sessionCount"] == 2
    assert "sessions" not in ev["coverage"]


def test_prompt_cites_both_findings_and_leaks_no_participant_rows():
    """Acceptance: both findings are cited as evidence; and the FR-ETH-4
    grep - no participant-row data reaches the prompt-construction output."""
    ev = retrospective.collect_evidence(
        "http://mw", "pilot-2026", None, fetch=_fake_fetch
    )
    prompt = retrospective.build_prompt(ev)
    # Both findings cited by requirement id.
    assert "FR-ING-3" in prompt and "FR-ANA-2" in prompt
    # No participant identifiers or per-session participant rows leak.
    assert "P01" not in prompt and "P02" not in prompt
    assert "participantId" not in prompt


def test_offline_bundle_lists_the_findings_as_a_template(tmp_path):
    ev = retrospective.collect_evidence(
        "http://mw", "pilot-2026", None, fetch=_fake_fetch
    )
    proposal, used_claude = retrospective.build_proposal(ev, client=None)
    assert used_claude is False
    # The evidence is fully assembled and cited for manual drafting.
    assert "FR-ING-3" in proposal and "FR-ANA-2" in proposal
    assert "## SRS amendments" in proposal
    assert "Explicitly rejected ideas" in proposal


def test_facilitator_notes_are_folded_in(tmp_path):
    notes = tmp_path / "findings.md"
    notes.write_text("# Facilitator findings\n\nDR-06: dev-host pass needed.\n")
    ev = retrospective.collect_evidence(
        "http://mw", "pilot-2026", notes, fetch=_fake_fetch
    )
    assert "DR-06" in retrospective.build_prompt(ev)


class _Block:
    type = "text"

    def __init__(self, text):
        self.text = text


class _Resp:
    def __init__(self, content):
        self.content = content


class FakeClaude:
    def __init__(self):
        self.messages = self

    def create(self, **kw):
        # Echo that it saw both findings, as a real proposal would cite them.
        assert "FR-ING-3" in kw["messages"][0]["content"]
        return _Resp([_Block(
            "## SRS amendments\n- FR-ING-3: amend - the seq-gap finding shows "
            "loss detection works [FR-ING-3].\n- FR-ANA-2: keep [FR-ANA-2].\n"
            "## Protocol-schema changes\nnone\n## Instrument config changes\n"
            "none\n## Explicitly rejected ideas\nnone\n"
        )])


def test_claude_draft_uses_the_evidence_and_marks_inert():
    ev = retrospective.collect_evidence(
        "http://mw", "pilot-2026", None, fetch=_fake_fetch
    )
    proposal, used_claude = retrospective.build_proposal(ev, client=FakeClaude())
    assert used_claude is True
    assert "Inert until reviewed" in proposal
    assert "FR-ING-3" in proposal and "FR-ANA-2" in proposal
