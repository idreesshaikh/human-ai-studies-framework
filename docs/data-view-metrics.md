# Data-view measures

The study workspace's **Data** tab shows collected data two ways: a per-session
**swimlane timeline** (every leg's events on one time axis) and a
**distribution panel** that compares one measure across conditions.

Historically the distribution panel charted only three static-code metrics;
every other measure the study collects was reachable only as a dot on the
swimlane. This page records which measures the panel now surfaces and the mark
each one uses.

## Scope

This is a completeness and accessibility improvement to an existing surface, not
a new product surface (see [scope.md](scope.md)): the feature set is frozen, and
this stays inside the existing Data tab — no new route, page, or navigation. The
data was already collected and already on the wire from
`GET /studies/{id}/dataset`; the panel simply stops discarding it.

## How measures are declared

Measures live in a single registry, `platform/src/lib/metricRegistry.ts`. Each
entry declares its `measurementType`, and the panel
(`platform/src/components/charts/MetricStrip.tsx`) dispatches the **mark** from
that type so each measure reads truthfully:

| Measurement type | Mark | Honest-stats rule |
| --- | --- | --- |
| continuous / count | jittered point strip; median line; IQR box only at n ≥ 5 | every observation drawn; per-cell `n` always shown |
| ordinal | counts per level, clustered by condition | an ordinal scale is a distribution, **never averaged** |
| categorical | per-condition share bar, weighted by volume | the `n` behind each share is shown |

Every mark has a table twin with exact numbers, and identity is never carried by
colour alone (legend + labels + table).

## Measures surfaced

Static-code metrics read `payload[key]` from `source == "metrics"` rows.
Event-derived measures read the event `type` from the one-timeline dataset.

| Measure | Source | Type | Related RQ |
| --- | --- | --- | --- |
| Cognitive complexity | static (`cognitive_complexity`) | continuous | RQ-P2 |
| Function inputs | static (`parameter_count`) | count | RQ-P2 |
| Nesting depth | static (`nesting_penalty`) | count | RQ-P2 |
| Identifier length | static (`avg_identifier_length`) | continuous | RQ-P2 |
| Scope distance (mean / max) | static (`mean_scope_distance`, `max_scope_distance`) | continuous | RQ-P2 |
| Halstead effort (function / file) | static (`halstead_effort`, `halstead_effort_total`) | continuous | RQ-P2 |
| Comment ratio | static (`comment_ratio`) | continuous | RQ-P2 |
| Indentation variance | static (`indentation_variance`) | continuous | RQ-P2 |
| Line width (mean / max) | static (`mean_line_width`, `max_line_width`) | continuous / count | RQ-P2 |
| Code authorship (AI vs human) | `edit_burst.origin` | categorical | RQ-P3 |
| AI-authored share | `edit_burst` (per participant) | continuous | RQ-P3 |
| AI character share (session) | `code_evolution.aiInsertionShare` | continuous | RQ-P3 |
| Lines per edit burst | `edit_burst.linesTouched` | count | RQ-P3 |
| Self-reported fatigue | `fatigue_response.value` (1–7) | ordinal | RQ-P1 |
| Comprehension probe correctness | `comprehension_probe_response.correct` | categorical | RQ-P1 |
| Agent response latency | `agent_turn.latencyMs` | continuous | RQ-P4 |
| Acceptance-test outcome | `task_outcome.passed` | categorical | RQ-P2 |

`correct` and `passed` fields that are `null` (ungradable / not applicable) are
dropped from a rate rather than scored, so a correct-rate reflects only probes
that were actually gradable. The "Related RQ" column is indicative, taken from
the pilot study's analysis plan; it is not resolved against each study's own
plan, so the app does not display it next to the chart.

## Adding a measure

Add an entry to `METRIC_REGISTRY` with its `measurementType` and an `extract`
function that pulls observations from dataset rows (key static metrics on
`payload[key]`; key event measures on the event `type`). The panel needs no
change — it renders whatever the registry returns. Add a case to
`platform/scripts/verify-metrics.mjs` for any non-trivial `extract` or derived
value.
