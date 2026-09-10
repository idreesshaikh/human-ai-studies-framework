# Scope

PHOENIX supports task-based studies of human–AI software development. It connects
study design, participant capture, and analysis handoff through an explicit
protocol.

The feature set is frozen for this release. Maintenance is limited to fixes,
security, accessibility, reproducibility, and documentation; new product
surfaces are out of scope.

## Supported work

- Configure questions, tasks, conditions, participants, measures, and an analysis
  plan from templates or a model-assisted conversation.
- Compile reviewed decisions into validated YAML.
- Derive assignment, consent, and instrumentation for TERN in VS Code.
- Collect study-scoped events and optional code or provider measurements.
- Rehearse capture and recipe compatibility with labelled synthetic data.
- Export datasets, dictionaries, notebooks, CLI reports, and replication kits.
- Explore literature and inspect planning calculations with stated assumptions.

The `curated` package is retained as an experimental mining contract. It only
supports local archive fixtures today; it is not part of the supported live
workflow and its authorship signals are hypotheses, not ground truth.

## Outside this project

PHOENIX does not grant ethics approval, recruit participants, enforce university
workflows, or certify statistical validity. It is not a general research
assistant, a paper-writing service, or an orchestrator for arbitrary external
providers.
There is no lifecycle board, presence service, amendment approval workflow, or
community template moderation queue.

## Constraints

Researchers approve consequential choices. The model proposes changes but cannot
bypass protocol validation. Source links must resolve to retrieved records;
unsourced proposals remain identifiable.

Capture follows the disclosed configuration. TERN excludes source text,
keystrokes, and clipboard content. External transcript and snapshot tools have
separate policies that must be reviewed before use.

Reads and exports respect project access and session attribution. Network failure
cannot turn a failed write into a successful local simulation. Synthetic rows
must be identifiable and excluded from participant findings.

Schema compatibility matters when retiring features: do not delete existing
protocol fields or database records merely to reduce code size.
