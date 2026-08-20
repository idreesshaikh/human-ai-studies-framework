"""Unit tests for the pure protocol compiler's template resilience."""

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
    """
    The original bug: an accepted choose-template move naming a template the registry
    doesn't have crashed the compile.
    """
    result = compiler.compile_moves(
        [_rq_move(), _template_move("m-t", "hallucinated-rct-2026", {})]
    )
    assert result.yaml.strip(), "the draft must never come back empty"
    assert not result.valid
    assert any("m-t" in e and "hallucinated-rct-2026" in e for e in result.errors)
    assert "the design" in result.unresolved


def test_unknown_parameters_are_ignored_with_a_warning():
    """
    An LLM-invented parameter name doesn't sink an otherwise-sound template choice —
    it's dropped, noted, and the template still applies.
    """
    result = compiler.compile_moves(
        [_template_move("m-t", "two-group-rct-v1", {"bogusParam": 999})]
    )
    assert result.template_id == "two-group-rct-v1"
    assert result.valid
    assert any("bogusParam" in w for w in result.warnings)
    assert not result.errors


def test_last_instantiable_template_wins_over_a_broken_later_one():
    """
    A broken accepted template move is skipped in favour of the most recent one that
    instantiates, and the skip is reported as a warning — a valid draft isn't blocked on
    a move nobody can un-accept.
    """
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


def test_list_valued_patch_flattens_into_string_entries():
    """A move that packs several entries into one list value ("Two conditions: A vs."""
    conditions = {
        "moveId": "m-c",
        "kind": "set-parameter",
        "target": "conditions",
        "proposal": "Two conditions.",
        "patch": {
            "section": "conditions",
            "op": "append",
            "value": ["AI-assisted", "Traditional resources"],
        },
        "grounding": [],
        "status": "accepted",
    }
    result = compiler.compile_moves(
        [_template_move("m-t", "two-group-rct-v1", {}), conditions]
    )
    assert result.valid, result.errors
    assert "AI-assisted" in result.draft["conditions"]
    assert "Traditional resources" in result.draft["conditions"]
    assert all(isinstance(c, str) for c in result.draft["conditions"])


def test_broken_template_before_a_working_one_stays_silent():
    """
    Last-wins semantics unchanged: when the newest accepted template move instantiates,
    earlier ones — broken or not — are simply superseded.
    """
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
