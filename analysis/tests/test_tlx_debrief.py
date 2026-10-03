"""
Regression for #67: the TLX debrief recipe must consume the real extension debrief
contract end to end.

The extension emits ``end_survey_response`` (not ``end_survey``) with a *nested*
payload ``{responses, comments, msToComplete}``, and dismissals as
``end_survey_skipped``. The recipe used to read ``end_survey`` and treat every numeric
column as a subscale, which (a) found nothing on real data and (b) would have counted
``msToComplete`` as a rating. This test feeds the real contract through
``Dataset`` -> ``tlx-debrief`` and pins the fixed behaviour.
"""

import analysis.recipes  # noqa: F401 - populate the registry
from analysis.core import REGISTRY
from analysis.dataset import Dataset


def _response(session, participant, condition, responses, ms):
    return {
        "source": "tern",
        "ts": "2026-07-11T10:57:00.000Z",
        "sessionId": session,
        "participantId": participant,
        "condition": condition,
        "type": "end_survey_response",
        "seq": 20,
        "flags": [],
        "payload": {
            "responses": responses,
            "comments": "some free text that is not a rating",
            "msToComplete": ms,
        },
    }


def _skipped(session, participant, condition):
    return {
        "source": "tern",
        "ts": "2026-07-11T14:10:00.000Z",
        "sessionId": session,
        "participantId": participant,
        "condition": condition,
        "type": "end_survey_skipped",
        "seq": 20,
        "flags": [],
        "payload": {},
    }


# The exact NASA-TLX item set the extension's end survey emits
# (extension/src/core/surveys.ts END_SURVEY_ITEMS). showEndSurvey renders these six
# in every condition; the declared `ai_reliance` item is not wired into the survey, so
# it is deliberately not represented here.
_SUBSCALES = ("mental_demand", "effort", "frustration", "time_pressure",
              "perceived_performance", "comprehension")


def _responses(seed: int) -> dict:
    return {k: 1 + (seed + i) % 7 for i, k in enumerate(_SUBSCALES)}


def _dataset():
    rows = [
        _response("S1", "P01", "ai-assisted", _responses(1), 41000),
        _response("S2", "P02", "unassisted", _responses(2), 53000),
        _response("S3", "P03", "ai-assisted", _responses(3), 38000),
        _response("S4", "P04", "unassisted", _responses(4), 61000),
        _skipped("S5", "P05", "ai-assisted"),
    ]
    return Dataset(rows=rows, study_id="synthetic")


def test_real_debrief_response_produces_subscales():
    """All six nested response items become subscales on real debrief data."""
    result = REGISTRY["tlx-debrief"].run(_dataset())
    subscales = set(result.tables["per_condition"]["subscale"])
    assert subscales == set(_SUBSCALES)


def test_completion_time_and_comments_are_not_rated():
    """``msToComplete`` and ``comments`` share the payload but are never subscales."""
    result = REGISTRY["tlx-debrief"].run(_dataset())
    subscales = set(result.tables["per_condition"]["subscale"])
    assert "msToComplete" not in subscales
    assert "comments" not in subscales
    # Belt and braces: the prefixed column name must not survive either.
    assert not any(s.startswith("responses.") for s in subscales)


def test_skipped_survey_counts_as_a_non_response():
    """A dismissed survey is counted as a non-response, never rated."""
    result = REGISTRY["tlx-debrief"].run(_dataset())
    assert "4 responded, 1 skipped" in result.summary
