# Design model readiness

The design assistant needs short, structured JSON responses with actionable
protocol patches, not a long free-form answer. Provider availability is part of
demo readiness: a listed model is not necessarily callable with a particular key.

## Configuration

`MISTRAL_MODEL` selects the shared model for design and corpus matching.
`MISTRAL_DESIGN_MODEL` optionally overrides only design. Empty values are treated
as unset. The default is `ministral-14b-latest`; resolve settings at client
creation, not module import. No model key means the existing offline workflow.
Use a dated model ID for a reproducible research run.

## Small compatibility check, 2026-10-05

Using the existing developer key, send a synthetic Python debugging study brief
through the application's real `design_llm.propose_turn` parser, with JSON response
format and its normal 1,200-token output cap. No participant data was submitted.

| Model | Result | Time |
| --- | --- | --- |
| `mistral-medium-latest` | HTTP 429; no usable turn | 0.17 s |
| `mistral-small-latest` | HTTP 429; no usable turn | 0.44 s |
| `ministral-14b-latest` | Valid turn, one `add-rq` proposal with a patch | 2.62 s |

A separate Ministral streaming request also produced streamed prose and a valid
`add-rq` patch through `propose_turn_streaming` in 1.71 s.

Ministral is the demonstrated working default for this key. This single prompt
does **not** establish a model-quality ranking, methodological correctness,
long-run reliability, or that the other models are broken. Limits can change.
The `/models` response listed Medium and Small, but actual requests failed.

## Choosing a stronger model later

Mistral describes [Medium 3.5](https://docs.mistral.ai/models/mistral-medium-3-5-26-04)
as a frontier-class model with structured output support. It remains a candidate
when this key's limits permit it. [Free usage and limits](https://docs.mistral.ai/admin/billing-usage/usage-limits)
depend on the organisation and model; switching cannot guarantee quota relief.

For issue #47, a full upgrade decision still needs held-out briefs, expert review
of grounded choices and patch correctness, repeated latency/failure measurements,
and input/output-token cost accounting. Do not treat this availability check as
that evaluation or as proof of scientific recommendation quality.

## Presentation fallback

Keep an approved study ready before presenting. If model suggestions fail, the
conversation preserves the message and applies no proposal. Allow a cooldown,
or use manual authoring. Validation, participant assignment, capture, synthetic
rehearsal, and exports do not require a model key. Do not silently substitute
another model: an experiment's model selection should remain explicit.
