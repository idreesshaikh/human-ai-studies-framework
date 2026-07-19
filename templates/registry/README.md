# Registry templates (a seed set, meant to grow)

A **template** encodes one *published* study design (its structure, its
prescribed statistics, its required instruments) so a researcher can
instantiate it into a valid protocol with zero hand edits. The registry
is designed as an **expandable library**: the published literature holds
hundreds of distinct designs, and each becomes a template as its recipes
and instruments come online. What lives here now is a **thin seed** that
proves the mechanism, not the finished library:

- **metr-rct-v1** — the METR early-2025 developer-productivity RCT
  (arxiv:2507.09089): within-subjects, objective outcomes + perception.
- **ziegler-telemetry-survey-v1** — the Ziegler acceptance-rate
  telemetry-plus-survey design.

A template enters this directory only once `validate_registry()` passes
for it (schema, mandatory citations, every recipe exists, and every
skeleton placeholder is a declared parameter). Designs whose dependencies
aren't built yet wait in `../drafts/`.

## A template is not a study

Templates are platform library content. A **study** — including the
owner's trial studies that prove the platform works — is a protocol
instance in `protocol/examples/`, authored via the design conversation.
A study *may* start from a template, but it does not have to, and it is
never itself a template. There is no template-per-study expectation: the
library grows with the *literature*, not with the studies run here.
