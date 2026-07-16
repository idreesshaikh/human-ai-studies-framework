# Task B - "logbook" (matched pair: Task A "expenses")

The second of the two matched Python maintenance tasks of the frozen pilot
protocol. See `task-a-expenses.md` for the comparability contract and the
FR-INST-16 harness note (MP-12); everything there applies symmetrically.

## What the participant receives

A small, working-but-buggy Python 3.12 command-line tool (~150 lines, three
modules: `parse.py`, `aggregate.py`, `report.py`) that reads a plaintext
web-server access log and prints per-endpoint latency statistics. The repo
contains a `README.md`, sample log data, and a pytest acceptance suite
(8 tests, 3 initially failing).

## The work (45 minutes)

Ordered by priority; partial completion is expected and fine:

1. **Defect 1 (boundary):** request/response pairs that span midnight get a
   negative duration and are silently dropped from the stats (a same-day
   assumption in the timestamp pairing).
2. **Defect 2 (aggregation):** the percentile helper mis-indexes on small
   samples (off-by-one), so p95 latency is reported from the wrong
   observation whenever an endpoint has fewer than 20 requests.
3. **Feature:** add a `--slow N` flag that lists the N slowest requests per
   endpoint (ties broken by timestamp, stable across runs), covered by the
   two already-written failing acceptance tests.
