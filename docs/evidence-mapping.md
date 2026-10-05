# Study-evidence mapping contract

The first implementation of #89 is a separate, versioned evidence-map document
owned by `protocol.evidence`. It can be validated without a model or server:

```bash
uv run protocol validate-evidence-map protocol/examples/evidence-map.yaml
uv run protocol evidence-map-schema
```

The example is explicitly synthetic. Its passages are invented contract
fixtures, not citations or evidence of methodological suitability. Applicable,
incompatible and insufficient-evidence cases are checked in the contract tests;
those tests do not constitute expert review of a research dataset.

## Identity and unknowns

`schemaVersion` versions the contract; `mapId` and `mapVersion` identify a map
snapshot. Publications carry a stable source identifier (for example a DOI,
arXiv id, corpus id or immutable document URL), title and source version. One
publication may report several empirical studies; one study may have several
reports. Reuse identities instead of counting those reports as separate studies.

Each empirical study records its research questions, design family, population,
tasks, conditions, constructs, measures, analysis assumptions, limitations and
capture requirements. Unknown facts are `null`; empty lists mean no entries
recorded, not proof that no limitations or assumptions exist. A measure names
its construct, instrument, dataset fields and analysis recipe separately. A
capture requirement references that measure and records whether collection is
available, external, unavailable or unknown. These are annotations, not a
substitute for executable protocol validation or a capability check.

## Evidence and review

Relations distinguish reported method use, methodological guidance, measurement
validity and conditional applicability. Every relation carries a source passage
and its location, a claim, and whether that claim is a reported fact,
interpretation or recommendation. Reporting use never establishes validity.

Review status is unreviewed, reviewed or disputed. Reviewed entries require an
identified reviewer; notes retain review rationale or disagreement. This field
records a claim of review, not verification of a person's identity. Pilot-map
curation still needs source verification and independent review under #91.

Extraction confidence is nullable and bounded to 0–1. Evidence quality has its
own explicit categories. Neither is an applicability probability. Retrieval
and popularity scores are deliberately absent from the evidence contract.

Applicability is assessed for a stated context, with reasons, constraints and
missing facts. Its status is compatible, conditional, incompatible or unknown.
Unreviewed or disputed relations must retain unknown applicability. Conditional
decisions require an explicit constraint or missing fact. Downstream ranking
must recompute applicability when that context changes; the contract does not
yet implement ranking or researcher decisions.

## Delivery boundary

This delivers the machine-readable foundation of #90 and does not claim the
reviewed pilot map, evidence ranking, protocol traceability, researcher UI or
held-out benchmark are complete. The existing protocol schema and approval path
remain authoritative. #91–#98 need reviewed sources and evaluation; no classifier
is added before the adoption criteria are met.
