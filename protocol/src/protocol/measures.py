"""Typed measures and protocol-declared survey scoring. Legacy data is untyped."""

import math


def normalized_measures(protocol: dict) -> list[dict]:
    return [
        m
        if isinstance(m, dict)
        else {
            "id": f"legacy-{i + 1}",
            "construct": m,
            "instrument": None,
            "fields": [],
            "analysisRecipe": None,
            "legacy": True,
        }
        for i, m in enumerate(protocol.get("measures", []))
    ]


def score_survey(instrument: dict, responses: dict) -> float | None:
    """Missing items yield no aggregate; reverse scoring precedes the rule."""
    values = []
    for item in instrument["items"]:
        value = responses.get(item["id"])
        scale = item["scale"]
        if not isinstance(value, (float, int)) or isinstance(value, bool):
            return None
        if not math.isfinite(value) or not scale["min"] <= value <= scale["max"]:
            return None
        step = scale.get("step", 1)
        if not math.isclose(
            (value - scale["min"]) / step, round((value - scale["min"]) / step)
        ):
            return None
        if item.get("reverse", False):
            value = scale["min"] + scale["max"] - value
        if instrument["scoring"] == "sus":
            value -= scale["min"]
        values.append(value)
    if not values or instrument["scoring"] == "none":
        return None
    if instrument["scoring"] == "sus":
        return sum(values) * 2.5
    if instrument["scoring"] == "sum":
        return sum(values)
    return sum(values) / len(values)


def shipped_instruments() -> list[dict]:
    """Candidate instruments with explicit wording, licence and validation notes."""
    import json
    from importlib import resources

    return json.loads(
        resources.files("protocol")
        .joinpath("schema/survey-instruments.json")
        .read_text("utf-8")
    )


def validated_responses(instrument: dict, responses: dict) -> bool:
    if not isinstance(responses, dict):
        return False
    for item in instrument["items"]:
        value = responses.get(item["id"])
        scale = item["scale"]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            return False
        index = (value - scale["min"]) / scale.get("step", 1)
        if not scale["min"] <= value <= scale["max"] or not math.isclose(
            index, round(index)
        ):
            return False
    return True
