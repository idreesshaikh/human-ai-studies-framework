"""The steer dial (FR-CONV-9): how much the assistant drives a conversation."""

from middleware.design_assistant import _directive, _permitted_moves

from middleware import elicitation


class _Move:
    """The two fields ``_permitted_moves`` reads off a proposed move."""

    def __init__(self, kind: str) -> None:
        self.kind = kind


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


def test_every_level_names_a_register_and_an_initiative():
    """
    Both levers, for every stop  -  a level that only changed the register would make
    the dial a duplicate of the profile setting in Settings.
    """
    for key, spec in elicitation.STEER_LEVELS.items():
        assert spec["profile"] in elicitation.PROFILES, key
        assert spec["guidance"].strip(), key
        assert elicitation.steer_profile(key) == spec["profile"]


def test_an_unknown_or_absent_level_falls_back_rather_than_going_silent():
    """
    An older client, or an agent posting a turn without the field, must still get a full
    instruction  -  never an empty one.
    """
    assert elicitation.steer_guidance(None) == (
        elicitation.STEER_LEVELS[elicitation.DEFAULT_STEER]["guidance"]
    )
    assert elicitation.steer_guidance("nonsense") == (
        elicitation.STEER_LEVELS[elicitation.DEFAULT_STEER]["guidance"]
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


def test_a_talkative_level_keeps_every_move():
    moves = (_Move("choose-template"), _Move("add-measure"), _Move("caution"))
    kept = _permitted_moves(moves, _stance(steer="leads"))
    assert [m.kind for m in kept] == ["choose-template", "add-measure", "caution"]


def test_the_directive_carries_both_levers_into_the_prompt():
    """The model is told who it is speaking to AND how much to drive, in that order."""
    directive = _directive(_stance(steer="checks", profile="experienced"))
    assert elicitation.PROFILES["experienced"]["guidance"] in directive
    assert elicitation.STEER_LEVELS["checks"]["guidance"] in directive


def test_the_dial_never_changes_the_method():
    """
    The guardrail behind the whole feature: no level may promise different designs,
    weaker statistics, or softer grounding.
    """
    forbidden = ("simpler statistic", "skip the", "no need to cite", "approximate")
    for key, spec in elicitation.STEER_LEVELS.items():
        lowered = spec["guidance"].lower()
        for phrase in forbidden:
            assert phrase not in lowered, f"{key} weakens the method: {phrase}"


def test_a_conversation_nobody_has_tuned_drives_itself():
    """The untouched default asks one question at a time and names the move."""
    assert elicitation.DEFAULT_STEER == "leads"
    assert "ONE question per turn" in elicitation.steer_guidance(None)


def test_the_default_still_proposes():
    """
    Driving is not the same as going quiet: the default must still put moves forward, or
    the conversation cannot build a protocol at all.
    """
    assert elicitation.proposals_permitted(None)
