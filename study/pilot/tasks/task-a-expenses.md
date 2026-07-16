# Task A - "expenses" (matched pair: Task B "logbook")

One of the two matched Python maintenance tasks of the frozen pilot
protocol (`protocol/examples/pilot-study.yaml`, session.taskDescription).
The task repository and its acceptance-test harness ship with MP-12
(FR-INST-16); this document freezes the task *design* so the pair stays
comparable and the ethics application can describe exactly what
participants do.

## What the participant receives

A small, working-but-buggy Python 3.12 command-line tool (~150 lines, three
modules: `parse.py`, `aggregate.py`, `report.py`) that reads a CSV of
personal expense records and prints a per-month spending report. The repo
contains a `README.md` (usage + how to run tests), sample data, and a
pytest acceptance suite (8 tests, 3 initially failing).

## The work (45 minutes)

Ordered by priority; partial completion is expected and fine:

1. **Defect 1 (boundary):** records dated with single-digit months/days
   (`2026-7-4`) crash the parser; the report also drops every record on the
   last day of a month (an exclusive-bound bug in the month bucketing).
2. **Defect 2 (aggregation):** refunds (negative amounts) are added to
   category totals with `abs()`, silently inflating monthly totals.
3. **Feature:** add a `--top N` flag that lists the N largest expenses per
   month (ties broken by date, stable across runs), covered by the two
   already-written failing acceptance tests.

## Comparability contract with Task B

| Dimension | Both tasks |
| --------- | ---------- |
| Size / structure | ~150 lines, parse → aggregate → report modules |
| Defect 1 | date/time boundary bug crossing a unit edge |
| Defect 2 | aggregation bug that silently skews totals |
| Feature | a top-N report flag with stable ordering |
| Tests | 8 pytest acceptance tests, 3 failing at start |
| Domain knowledge | none beyond everyday concepts (money / server logs) |

## Outcome ground truth (FR-INST-16)

The harness (MP-12) runs the acceptance suite at session end (and on save,
optionally) and emits `task_outcome` events - pass/fail counts and
time-to-first-green - consumed by the `task-outcome-by-condition` recipe.
