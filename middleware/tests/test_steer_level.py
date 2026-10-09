"""The steer dial (FR-CONV-9): how much the assistant drives a conversation."""

from middleware.design_assistant import _directive, _permitted_moves

from middleware import elicitation


class _Move:
    """The two fields ``_permitted_moves`` reads off a proposed move."""

    def __init__(self, kind: str) -> None:
        self.kind = kind


class _SectionMove(_Move):
    def __init__(self, kind: str, section: str) -> None:
        super().__init__(kind)
        self.patch = {"section": section}


def _stance(**over) -> dict:
    base = {
        "intent": "statement",
        "steer": None,
        "profile": None,
        "understanding": {
            "missing": [],
            "missingLabels": [],
            "known": ["a", "b", "c", "d", "e"],
            "facetsNeeded": 5,
        },
        "nextQuestion": None,
        "namedDesign": False,
        "mayProposeDesign": True,
        "mayProposeMoves": True,
    }
    base.update(over)
    return base


def test_an_unknown_or_absent_level_falls_back_rather_than_going_silent():
    """
    An older client, or an agent posting a turn without the field, must still get a full
    instruction  -  never an empty one.
    """
    assert (
        elicitation.steer_guidance(None)
        == (elicitation.STEER_LEVELS[elicitation.DEFAULT_STEER]["guidance"])
    )
    assert (
        elicitation.steer_guidance("nonsense")
        == (elicitation.STEER_LEVELS[elicitation.DEFAULT_STEER]["guidance"])
    )
    assert elicitation.steer_profile(None) is None


def test_only_the_quietest_level_closes_the_proposal_gate():
    assert elicitation.proposals_permitted("leads")
    assert elicitation.proposals_permitted("guides")
    assert elicitation.proposals_permitted("assists")
    assert not elicitation.proposals_permitted("checks")
    # Absent and unknown both mean "the researcher never moved the dial".
    assert elicitation.proposals_permitted(None)
    assert elicitation.proposals_permitted("nonsense")


def test_checks_drops_proposals_but_never_drops_a_caution():
    """The enforcement half."""
    moves = (
        _Move("choose-template"),
        _Move("add-measure"),
        _Move("caution"),
    )
    kept = _permitted_moves(moves, _stance(steer="checks", mayProposeMoves=False))
    assert [m.kind for m in kept] == ["caution"]


def test_every_level_keeps_one_decision_at_a_time():
    moves = (_Move("choose-template"), _Move("add-measure"), _Move("caution"))
    kept = _permitted_moves(moves, _stance(steer="leads"))
    assert [m.kind for m in kept] == ["caution"]


def test_a_complete_brief_can_return_the_whole_safe_batch():
    moves = (_Move("choose-template"), _Move("add-measure"), _Move("caution"))
    kept = _permitted_moves(moves, _stance(steer="leads", batchIntake=True))
    assert [m.kind for m in kept] == [
        "choose-template",
        "add-measure",
        "caution",
    ]


def test_assists_only_keeps_one_move_for_an_empty_section():
    moves = (
        _SectionMove("add-measure", "measures"),
        _SectionMove("add-rq", "researchQuestions"),
        _Move("caution"),
    )
    kept = _permitted_moves(
        moves,
        _stance(steer="assists"),
        {"filled": ["measures"]},
    )
    assert [m.kind for m in kept] == ["caution"]


def test_missing_facets_still_allow_one_safe_concrete_move():
    stance = _stance(
        intent="describe",
        steer="leads",
        understanding={
            "missing": ["task"],
            "missingLabels": ["the programming task"],
            "known": ["population"],
            "facetsNeeded": 5,
        },
        nextQuestion="What will participants do?",
        mayProposeDesign=False,
    )
    directive = _directive(stance)
    assert "record only that safe fact as one move" in directive
    assert "Do not add a different protocol move" not in directive
