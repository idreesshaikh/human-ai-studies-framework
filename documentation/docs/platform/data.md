# Data

The Data tab answers the question every researcher needs answered before
analysis: **what arrived, how complete is it, and is it live or rehearsal data?**

<figure markdown="span">
  ![The current Phoenix Data tab](../assets/screens/phoenix-demo-data-current.png){ width="900" }
  <figcaption>Complete sessions stay visible beside an intentional sequence-gap warning; the platform does not quietly repair evidence.</figcaption>
</figure>

## Two paths, one schema

- **Live capture** — TERN’s cognitive, behavioural, static-metrics, and agent
  legs, configured per study from the approved protocol.
- **Curated import** — archive adapters with a validity-threats record, for
  studies that began elsewhere.

Both paths converge on the same event and metric schema, so the analysis plan
does not change depending on how a row entered the project.

## Synthetic dry run

Before recruiting, send simulated participants through the real ingest and
analysis path:

```bash
uv run python -m middleware simulate pilot-2026 --count 10 --seed 42
```

The run validates every recipe in the study’s analysis plan and exits non-zero
if the plan cannot be satisfied. This is a plumbing and design check, not an
empirical result.

## Integrity is a first-class result

The Data tab exposes event counts, metric rows, and sequence gaps per session.
A red `sequence-gap` marker means events are missing from the expected sequence;
it does not mean the platform guessed what happened. Complete and incomplete
sessions remain distinguishable for the researcher’s decision.

The banner also distinguishes built-in sample data from a live middleware
connection. Screenshots and demo rows are useful for understanding the UI, never
for making a claim about participants.

## Recruitment planning

The Planning tab shows the power/sensitivity curve for the planned comparison,
including the assumptions behind the target and the total `n` needed across
plausible effect sizes. It keeps a sample-size decision attached to the protocol
instead of burying it in a later notebook.

## The analysis hand-off

The protocol that configured TERN also produces the hand-off:

- **`notebook`** — a loaded, documented dataframe with planned recipes and a
  standalone `data-dictionary.md`;
- **`paper`** — a first-draft Methods + Results section from the same plan;
- **`run` / `validate` / `list`** — execute recipes, check plan satisfaction, and
  catalogue what exists.

The research team still owns the final analysis and interpretation. PHOENIX
makes the inputs, assumptions, and integrity decisions inspectable.

!!! warning "Synthetic means synthetic"
    The checked-in `demo-study` data is illustrative. Never present it as a
    finding or combine it with a live result without an explicit provenance rule.
