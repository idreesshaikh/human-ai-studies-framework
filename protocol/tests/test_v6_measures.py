import copy
from pathlib import Path

import pytest
from protocol.capture import producer_capabilities
from protocol.derive import derive_overlay_settings
from protocol.loader import load_protocol, validate_protocol
from protocol.measures import (
    normalized_measures,
    score_survey,
    score_survey_scales,
    shipped_instruments,
)
from protocol.versioning import (
    compare_designs,
    content_hash,
    provenance,
    version_record,
)

EXAMPLE = Path(__file__).parents[1] / "examples/planner-v6.yaml"


def test_v6_round_trip_and_legacy_versions_remain_untyped(pilot_doc, write_protocol):
    v6 = load_protocol(EXAMPLE)
    assert load_protocol(write_protocol(v6)) == v6
    for version in range(1, 6):
        doc = copy.deepcopy(pilot_doc)
        doc["protocolVersion"] = version
        if version <= 3:
            doc["instruments"]["kite"] = doc["instruments"].pop("tern")
        doc["measures"] = ["Task completion time"]
        assert not validate_protocol(doc)
        loaded = load_protocol(write_protocol(doc))
        assert normalized_measures(loaded)[0]["legacy"]
        assert loaded["measures"] == ["Task completion time"]
        assert (
            derive_overlay_settings(loaded, "P01", loaded["conditions"][0])[
                "tern.session.durationMinutes"
            ]
            == loaded["session"]["durationMinutes"]
        )
        assert producer_capabilities(loaded)["tern"]["configured"]


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.update(measures=["Old free text"]),
        lambda p: p["measures"][0].update(instrument="missing"),
        lambda p: p["measures"][0].update(analysisRecipe="not-in-plan"),
        lambda p: p["measures"].append(p["measures"][0].copy()),
        lambda p: p["instruments"]["surveys"][0]["items"][0]["scale"].update(max=0),
        lambda p: p["covariate"].update(instrument="raw-tlx"),
        lambda p: p["instruments"]["surveys"][0]["items"][0]["scale"].update(
            max=float("nan")
        ),
        lambda p: p["tasks"][0].update(description="changed without updating hash"),
        lambda p: p["toolVersions"].update(missing={"tool": "copilot"}),
    ],
)
def test_invalid_typed_links_scales_covariates_and_hashes_are_rejected(change):
    doc = load_protocol(EXAMPLE)
    change(doc)
    assert validate_protocol(doc)


def test_shipped_instrument_scoring_reverse_missing_and_scale_checks():
    instruments = {i["id"]: i for i in shipped_instruments()}
    sus = instruments["sus"]
    best = {i["id"]: 1 if i.get("reverse") else 5 for i in sus["items"]}
    assert score_survey(sus, best) == 100
    assert score_survey(sus, dict.fromkeys(best, 3)) == 50
    assert score_survey(sus, {}) is None
    assert score_survey(sus, {**best, "sus_1": 6}) is None
    tlx = instruments["raw-tlx"]
    assert score_survey(tlx, {i["id"]: 50 for i in tlx["items"]}) == 50
    assert score_survey(tlx, {i["id"]: 55 for i in tlx["items"]}) is None
    # Rated a perfect performance with no load: zero workload, TLX direction.
    calm = {i["id"]: 100 if i["id"] == "performance" else 0 for i in tlx["items"]}
    assert score_survey(tlx, calm) == 0
    check = instruments["session-check"]
    assert score_survey(check, {"ai_use": 0, "comprehension": 5}) is None
    assert "Unvalidated" in instruments["pre-task-skill"]["validation"]
    assert all(
        i.get("source") and i.get("licence") and i.get("validation")
        for i in instruments.values()
    )


def test_bfi_2_xs_follows_the_published_extra_short_key():
    xs = {i["id"]: i for i in shipped_instruments()}["bfi-2-xs"]
    # Soto & John (2017): E 1R 6 11, A 2 7R 12, C 3R 8R 13, N 4 9 14R, O 5 10R 15.
    assert [n for n, item in enumerate(xs["items"], 1) if item["reverse"]] == [
        1,
        3,
        7,
        8,
        10,
        14,
    ]
    assert [len(group["items"]) for group in xs["scales"]] == [3] * 5
    high = {i["id"]: 1 if i["reverse"] else 5 for i in xs["items"]}
    assert set(score_survey_scales(xs, high).values()) == {5}
    assert score_survey(xs, high) is None  # domains only, no total


def test_hashes_are_content_addressed_and_lineage_never_pools():
    original = load_protocol(EXAMPLE)
    rerun = copy.deepcopy(original)
    rerun["rerunOf"] = content_hash(original)
    rerun["toolVersions"]["tool-version-a"]["version"] = "recorded-test-version"
    assert content_hash(original) != content_hash(rerun)
    assert provenance(original)["measureSet"]["sha256"] == content_hash(
        original["measures"]
    )
    assert (
        version_record(original["tasks"][0])["sha256"]
        == original["tasks"][0]["contentHash"]
    )
    compared = compare_designs(original, rerun)
    assert not compared["pooled"]
    assert next(f for f in compared["fields"] if f["field"] == "toolVersions")[
        "changed"
    ]
