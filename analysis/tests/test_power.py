"""Power/sensitivity curve planning math (P2-2).

The bar: exact math (non-central t, not a normal approximation), textbook
anchors (d=0.8 at 80% power needs 26 per group; d=0.5 needs ~64 per group
— both two-sample, two-sided, alpha 0.05), monotone power in n and d,
explicit "not reached within range" rather than a false number, and
determinism.
"""

from __future__ import annotations

import pytest
from analysis.power import two_sample_power_curve


def test_textbook_anchors():
    """The two values every methods section checks against: 26 per group at
    d=0.8, ~64 per group at d=0.5 (alpha 0.05, 80% power, two-sided)."""
    r = two_sample_power_curve((0.8,), max_total_n=200)
    (req,) = r["requiredN"]
    assert req["nPerGroup"] == 26
    assert req["totalN"] == 52
    assert req["reachesTarget"]

    r = two_sample_power_curve((0.5,), max_total_n=200)
    (req,) = r["requiredN"]
    assert 62 <= req["nPerGroup"] <= 66


def test_power_is_monotone_in_n_and_effect_size():
    r = two_sample_power_curve((0.2, 0.5, 0.8), max_total_n=80)
    for curve in r["curves"]:
        powers = [p["power"] for p in curve["points"]]
        assert powers == sorted(powers), "power must not decrease with n"
    small, medium, large = r["curves"]
    for i in range(len(large["points"])):
        assert (
            large["points"][i]["power"]
            >= medium["points"][i]["power"]
            >= small["points"][i]["power"]
        )


def test_target_reached_only_within_range():
    r = two_sample_power_curve((0.5,), max_total_n=100)
    (req,) = r["requiredN"]
    assert req["nPerGroup"] is None and not req["reachesTarget"]
    r = two_sample_power_curve((0.5,), max_total_n=200)
    (req,) = r["requiredN"]
    assert req["reachesTarget"] and req["totalN"] <= 200


def test_first_crossing_is_the_smallest_sufficient_n():
    r = two_sample_power_curve((0.8,), max_total_n=200)
    (req,) = r["requiredN"]
    crossing = req["nPerGroup"]
    below = [p["power"] for p in r["curves"][0]["points"] if p["nPerGroup"] < crossing]
    assert not below or max(below) < 0.8
    assert req["powerAtTargetN"] >= 0.8


def test_deterministic_and_json_friendly():
    a = two_sample_power_curve((0.2, 0.5, 0.8), max_total_n=90)
    b = two_sample_power_curve((0.2, 0.5, 0.8), max_total_n=90)
    assert a == b
    import json

    json.dumps(a)  # must be JSON-serializable (the route returns it as-is)


def test_validation():
    with pytest.raises(ValueError):
        two_sample_power_curve((0.5,), alpha=1.0)
    with pytest.raises(ValueError):
        two_sample_power_curve((0.5,), power_target=0.0)
    with pytest.raises(ValueError):
        two_sample_power_curve((0.5,), max_total_n=3)
    with pytest.raises(ValueError):
        two_sample_power_curve(())
    with pytest.raises(ValueError):
        two_sample_power_curve((-0.2,))
