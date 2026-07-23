"""Unit tests for the pure protocol compiler's template resilience.

An accepted move can't be re-decided in the conversation UI, so a single
accepted choose-template move with a hallucinated template id or invented
parameters must never make ``compile_moves`` raise — that turned every
``/conversation/compile`` into a 500 and left the finish review claiming
the draft was empty despite dozens of accepted moves. The compiler reports
the broken move and keeps compiling (F1.3: named gaps, never silent ones —
and never a wedged study).
"""

from middleware import compiler


def _rq_move() -> dict:
    return {
        "moveId": "m-rq",
        "kind": "add-rq",
        "target": "researchQuestions[]",
        "proposal": "Do junior developers over-trust AI-generated code?",
        "patch": {
            "section": "researchQuestions",
            "op": "append",
            "value": "Do junior developers over-trust AI-generated code?",
        },
        "grounding": [],
        "status": "accepted",
    }


def _template_move(move_id: str, template_id: str, parameters: dict) -> dict:
    return {
        "moveId": move_id,
        "kind": "choose-template",
        "target": "design",
        "proposal": f"Use {template_id}.",
        "patch": {"templateId": template_id, "parameters": parameters},
        "grounding": [],
        "status": "accepted",
    }


def test_hallucinated_template_id_reports_instead_of_raising():
    """The original bug: an accepted choose-template move naming a template
    the registry doesn't have crashed the compile. Now it falls back to the
    scaffold, names the broken move in errors, and still emits YAML."""
    result = compiler.compile_moves(
        [_rq_move(), _template_move("m-t", "hallucinated-rct-2026", {})]
    )
    assert result.yaml.strip(), "the draft must never come back empty"
    assert not result.valid
    assert any("m-t" in e and "hallucinated-rct-2026" in e for e in result.errors)
    # No template applied → the unresolved slots are named, not hidden.
    assert "design" in result.unresolved


def test_unknown_parameters_are_ignored_with_a_warning():
    """An LLM-invented parameter name doesn't sink an otherwise-sound
    template choice — it's dropped, noted, and the template still applies."""
    result = compiler.compile_moves(
        [_template_move("m-t", "two-group-rct-v1", {"bogusParam": 999})]
    )
    assert result.template_id == "two-group-rct-v1"
    assert result.valid
    assert any("bogusParam" in w for w in result.warnings)
    assert not result.errors


def test_last_instantiable_template_wins_over_a_broken_later_one():
    """A broken accepted template move is skipped in favour of the most
    recent one that instantiates, and the skip is reported as a warning —
    a valid draft isn't blocked on a move nobody can un-accept."""
    result = compiler.compile_moves(
        [
            _rq_move(),
            _template_move("m-good", "two-group-rct-v1", {}),
            _template_move("m-bad", "hallucinated-rct-2026", {}),
        ]
    )
    assert result.template_id == "two-group-rct-v1"
    assert result.valid
    assert any("m-bad" in w for w in result.warnings)


def test_broken_template_before_a_working_one_stays_silent():
    """Last-wins semantics unchanged: when the newest accepted template move
    instantiates, earlier ones — broken or not — are simply superseded."""
    result = compiler.compile_moves(
        [
            _template_move("m-bad", "hallucinated-rct-2026", {}),
            _template_move("m-good", "two-group-rct-v1", {}),
        ]
    )
    assert result.template_id == "two-group-rct-v1"
    assert result.valid
    assert result.warnings == []
    assert result.errors == []
