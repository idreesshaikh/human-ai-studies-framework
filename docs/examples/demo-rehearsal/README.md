# AI cognitive load rehearsal handoff

This folder is a small, open-source handoff generated from the local
`AI cognitive load rehearsal` study after a real TERN participant rehearsal and
synthetic dry run.

- [`notebook.ipynb`](notebook.ipynb) is the starter notebook. It loads
  the dataset export, documents provenance, and imports the protocol-prescribed
  recipes without presenting synthetic output as a finding.
- [`data-dictionary.md`](data-dictionary.md) describes the event-first dataset
  and its payload fields.
- The complete walkthrough is [`../../demo-runbook.md`](../../demo-runbook.md).

The study is illustrative and uses anonymized demo IDs only. Generate a fresh
handoff from a local middleware instance for a real study.

> **Frozen snapshot.** This handoff predates the v4 debrief contract (issue #67):
> its debrief events use the earlier `end_survey` name and flat payload rather than
> `end_survey_response` with nested `responses`. It is kept as-is because it was
> produced from a one-off local rehearsal; regenerate from a current middleware
> instance for up-to-date field names.
