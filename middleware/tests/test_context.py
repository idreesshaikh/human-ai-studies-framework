"""
Fitting a design conversation into a context budget.

A long conversation cannot be sent whole. What survives the cut, and whether the
model is told anything was cut, decides whether it reasons about the study the
researcher actually described or about the tail end of it.
"""

from middleware.context import (
    ELISION_NOTE,
    TRUNCATION_NOTE,
    estimate_tokens,
    select_history,
)


def _turn(role: str, content: str) -> dict:
    return {"role": role, "content": content}


def _conversation(n: int, *, size: int = 40) -> list[dict]:
    """``n`` alternating turns, oldest first, each of roughly ``size`` characters."""
    return [
        _turn("user" if i % 2 == 0 else "assistant", f"turn{i:03d} " + "x" * size)
        for i in range(n)
    ]


# --- Token estimation --------------------------------------------------------


def test_token_estimate_grows_with_content_length():
    assert estimate_tokens([_turn("user", "x" * 400)]) > estimate_tokens(
        [_turn("user", "x" * 40)]
    )


def test_token_estimate_counts_every_turn():
    one = estimate_tokens([_turn("user", "x" * 100)])
    two = estimate_tokens([_turn("user", "x" * 100), _turn("assistant", "x" * 100)])

    assert two > one


def test_an_empty_conversation_estimates_to_nothing():
    assert estimate_tokens([]) == 0


# --- Selection ---------------------------------------------------------------


def test_a_conversation_within_budget_is_returned_whole():
    turns = _conversation(6)

    assert select_history(turns, budget_tokens=10_000) == turns


def test_an_empty_conversation_selects_nothing():
    assert select_history([], budget_tokens=10_000) == []


def test_a_conversation_over_budget_is_cut_down():
    turns = _conversation(200)

    selected = select_history(turns, budget_tokens=500)

    assert len(selected) < len(turns)
    assert estimate_tokens(selected) <= 500


def test_the_researchers_opening_framing_survives_a_long_conversation():
    turns = _conversation(200)

    selected = select_history(turns, budget_tokens=500)

    assert selected[0]["content"].startswith("turn000")
    assert any(t["content"].startswith("turn002") for t in selected)


def test_the_most_recent_turn_always_survives():
    turns = _conversation(200)

    selected = select_history(turns, budget_tokens=500)

    assert selected[-1]["content"].startswith("turn199")


def test_a_cut_conversation_tells_the_model_that_turns_are_missing():
    turns = _conversation(200)

    selected = select_history(turns, budget_tokens=500)

    notes = [t for t in selected if ELISION_NOTE in t["content"]]
    assert len(notes) == 1


def test_the_elision_note_sits_between_the_anchors_and_the_recent_turns():
    turns = _conversation(200)

    selected = select_history(turns, budget_tokens=500)
    index = next(i for i, t in enumerate(selected) if ELISION_NOTE in t["content"])

    assert selected[index - 1]["content"].startswith("turn00")
    assert selected[index + 1]["content"].startswith("turn1")


def test_the_elision_note_counts_the_turns_it_replaced():
    turns = _conversation(200)

    selected = select_history(turns, budget_tokens=500)
    note = next(t["content"] for t in selected if ELISION_NOTE in t["content"])
    dropped = len(turns) - (len(selected) - 1)

    assert str(dropped) in note


def test_an_uncut_conversation_carries_no_elision_note():
    selected = select_history(_conversation(6), budget_tokens=10_000)

    assert not any(ELISION_NOTE in t["content"] for t in selected)


def test_selection_preserves_chronological_order():
    selected = select_history(_conversation(200), budget_tokens=800)
    real = [t for t in selected if ELISION_NOTE not in t["content"]]

    assert real == sorted(real, key=lambda t: t["content"])


def test_a_budget_too_small_for_anything_still_respects_itself():
    selected = select_history(_conversation(200), budget_tokens=1)

    assert estimate_tokens(selected) <= 1


def test_one_enormous_turn_is_truncated_rather_than_dropped():
    turns = [*_conversation(4), _turn("user", "y" * 100_000)]

    selected = select_history(turns, budget_tokens=500)

    assert estimate_tokens(selected) <= 500
    assert any(TRUNCATION_NOTE in t["content"] for t in selected)


def test_a_turn_that_fits_is_never_truncated():
    selected = select_history(_conversation(6), budget_tokens=10_000)

    assert not any(TRUNCATION_NOTE in t["content"] for t in selected)
