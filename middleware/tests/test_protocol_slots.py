"""The protocol's slots: what a conversation must supply, and how it says so."""

from __future__ import annotations

import pytest

from middleware import compiler


def _append(move_id: str, section: str, value: str) -> dict:
    return {
        "moveId": move_id,
        "kind": "add-rq",
        "target": section,
        "proposal": value,
        "patch": {"section": section, "op": "append", "value": value},
        "grounding": [],
        "status": "accepted",
    }


def _field(move_id: str, path: tuple[str, ...], value: object) -> dict:
    return {
        "moveId": move_id,
        "kind": "set-field",
        "target": ".".join(path),
        "proposal": f"set {'.'.join(path)}",
        "patch": {"op": "set-field", "path": list(path), "value": value},
        "grounding": [],
        "status": "accepted",
    }


def _complete_moves() -> list[dict]:
    return [
        _append("a1", "researchQuestions", "Do juniors review AI code less?"),
        _append("a2", "conditions", "ai-assisted"),
        _append("a3", "conditions", "unassisted"),
        _field("f1", ("participants", "design"), "within-subjects"),
        _field("f2", ("participants", "planned"), 24),
        _field("f3", ("participants", "counterbalanced"), True),
        _field("f4", ("session", "durationMinutes"), 45),
        _field("f5", ("session", "taskDescription"), "A maintenance task"),
        _field("f6", ("study", "title"), "Junior review depth"),
        _field("f7", ("study", "ethicsRef"), "ETH-2026-114"),
        {
            "moveId": "i1",
            "kind": "add-instrument",
            "target": "instruments.tern",
            "proposal": "standard capture",
            "patch": {
                "section": "instruments",
                "op": "add-instrument",
                "name": "tern",
                "config": compiler.default_capture_instrument(45),
            },
            "grounding": [],
            "status": "accepted",
        },
        {
            "moveId": "p1",
            "kind": "prescribe-statistics",
            "target": "analysisPlan",
            "proposal": "Wilcoxon signed-rank",
            "patch": {"recipeId": "paired-nonparametric", "rq": "RQ-1"},
            "grounding": [],
            "status": "accepted",
        },
    ]


def test_a_conversation_reaches_a_valid_protocol_without_a_template():
    """The headline: a template is a shortcut, not the only road."""
    result = compiler.compile_moves(_complete_moves())
    assert result.valid, (result.errors, result.unresolved)
    assert result.unresolved == []
    assert result.template_id is None
    assert result.draft["participants"]["planned"] == 24
    assert result.draft["session"]["durationMinutes"] == 45


def test_ethics_reference_is_optional_for_protocol_readiness():
    moves = [
        move
        for move in _complete_moves()
        if move["patch"].get("path") != ["study", "ethicsRef"]
    ]
    result = compiler.compile_moves(moves)
    assert result.valid, (result.errors, result.unresolved)
    assert "ethics status or reference" not in result.unresolved


def test_filling_every_section_is_not_the_same_as_a_protocol():
    """The exact false-completeness bug, kept nailed down."""
    moves = [
        _append(f"a{i}", section, f"something for {section}")
        for i, section in enumerate(compiler.SECTIONS)
    ]
    result = compiler.compile_moves(moves)
    assert not result.valid
    assert result.unresolved, "an incomplete protocol must name what it lacks"
    assert "how many participants" in result.unresolved
    assert "how long a session runs" in result.unresolved


def test_the_scaffold_invents_nothing():
    """Absent stays absent."""
    result = compiler.compile_moves([_append("a1", "researchQuestions", "Q?")])
    assert "participants" not in result.draft
    assert "session" not in result.draft
    assert "instruments" not in result.draft
    assert "analysisPlan" not in result.draft
    assert "title" not in result.draft["study"]


def test_gaps_are_named_in_the_researcher_s_words_not_the_schema_s():
    result = compiler.compile_moves([_append("a1", "researchQuestions", "Q?")])
    assert "how many participants" in result.unresolved
    assert not any("is a required property" in e for e in result.errors)


def test_an_unexpected_schema_error_is_never_swallowed():
    """The error filter may only remove a message that has a plainer twin."""
    moves = [
        *_complete_moves(),
        _append("bad", "researchQuestions", "Q2?"),
    ]
    result = compiler.compile_moves(moves)
    assert result.valid, result.errors
    broken = compiler.compile_moves(
        [*_complete_moves(), _append("c9", "conditions", "")]
    )
    assert broken.unresolved == []


def test_template_gaps_are_still_reported():
    """
    ``unresolved`` used to short-circuit to ``[]`` the instant a template instantiated,
    reporting "nothing outstanding" for whatever it left open.
    """
    template = {
        "moveId": "t1",
        "kind": "choose-template",
        "target": "design",
        "proposal": "METR",
        "patch": {"templateId": "metr-rct-v1", "parameters": {}},
        "grounding": [],
        "status": "accepted",
    }
    result = compiler.compile_moves([template])
    assert result.unresolved == [
        slot.label for slot in compiler.unresolved_slots(result.draft)
    ]


@pytest.mark.parametrize(
    ("value", "expected"),
    [(24, 24), ("24", 24), (0, None), (-3, None), ("twenty-four", None), (True, None)],
)
def test_integer_slots_accept_the_same_answer_in_the_wrong_type_only(value, expected):
    """
    "24" is the right answer typed loosely and is taken; "twenty-four" is not a number
    and is refused rather than guessed at, because a silently mangled sample size is
    worse than an open slot.
    """
    result = compiler.compile_moves(
        [_field("f", ("participants", "planned"), value)]
    )
    assert result.draft.get("participants", {}).get("planned") == expected


def test_a_set_field_move_cannot_write_outside_the_declared_slots():
    """
    The conversation may fill the protocol's declared gaps and nothing more, so a model
    cannot invent structure by naming a new path.
    """
    result = compiler.compile_moves(
        [
            _field("f1", ("study", "id"), "hijacked"),
            _field("f2", ("literature",), ["fabricated"]),
        ]
    )
    assert result.draft["study"]["id"] == "draft"
    assert "literature" not in result.draft
    assert len(result.warnings) == 2
    assert all("not one of the protocol's fillable slots" in w for w in result.warnings)


def test_a_refused_value_is_warned_about_never_silently_dropped():
    result = compiler.compile_moves(
        [_field("f", ("participants", "design"), "sideways")]
    )
    assert any("not a valid enum" in w for w in result.warnings)


def test_false_is_an_answer_not_an_absence():
    """
    ``counterbalanced: false`` is a real methodological choice; the refusal signal is
    None specifically, never falsiness.
    """
    result = compiler.compile_moves(
        [_field("f", ("participants", "counterbalanced"), False)]
    )
    assert result.draft["participants"]["counterbalanced"] is False
    labels = [s.label for s in compiler.unresolved_slots(result.draft)]
    assert "whether condition order is counterbalanced" not in labels


def test_the_analysis_plan_compiles_to_the_shape_the_schema_accepts():
    """
    Regression: prescriptions used to compile to ``{id, params}`` objects, a shape no
    schema version has - every accepted prescription produced a protocol that could not
    validate.
    """
    result = compiler.compile_moves(_complete_moves())
    assert result.draft["analysisPlan"] == [
        {"rq": "RQ-1", "recipes": ["paired-nonparametric"]}
    ]
    assert result.valid, result.errors


def test_legacy_statistical_plan_sentence_is_recovered_as_a_runnable_recipe():
    """Old accepted cards must not leave the reopened draft permanently invalid."""
    moves = [move for move in _complete_moves() if move["moveId"] != "p1"]
    moves.append(
        _field(
            "legacy-statistics",
            ("statisticalPlan",),
            "Use a paired t-test after checking normality.",
        )
    )
    result = compiler.compile_moves(moves)
    assert result.valid, (result.errors, result.unresolved, result.warnings)
    assert result.draft["analysisPlan"] == [
        {"rq": "RQ-1", "recipes": ["paired-nonparametric"]}
    ]
    assert any("legacy statistical-plan" in warning for warning in result.warnings)
