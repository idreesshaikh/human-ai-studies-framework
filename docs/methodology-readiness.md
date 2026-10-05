# Methodology readiness

Scoped assessment for #56 and initial literature notes for #63, checked
2026-10-05. This is supporting guidance, not a new product workflow or a
certification of research quality.

## Standards and priorities

The [SIGSOFT checklist generator](https://www2.sigsoft.org/EmpiricalStandards/tools/)
assembles method-specific guidance. The [primary report, sections 2–3](https://arxiv.org/pdf/2010.03525)
describes general standards, method-specific standards, and supplements, with
expert judgment and justified deviations. Its review criteria target completed
empirical studies, not a software demo or pilot alone.

For the planned developer experiment, consult the General and Human-Participant
Experiment sections of the [current standards](https://www2.sigsoft.org/EmpiricalStandards/docs/standards),
plus the Human-Participant Ethics, Sampling, and Open Science
[supplements](https://www2.sigsoft.org/EmpiricalStandards/docs/supplements).
Our implementation assessment is:

| Priority | Existing support | Remaining research work |
| --- | --- | --- |
| P0: participant protection | Consent and scoped capture | Recruitment, risks, approval and withdrawal plan; #65 |
| P0: valid comparison | Deterministic assignment and order preview | Justify allocation; round-robin is not randomization |
| P1: measurement | Explicit instruments and recipe inputs | Establish construct validity; telemetry is not a validated proxy |
| P1: justified inference | Power assumptions and analysis recipes | Validate assumptions, uncertainty and deviations using actual data |
| P1: reproducibility | Protocol, dictionary and integrity bundle | Freeze task materials, versions, analysis and exclusions before collection |

These are recommendations, not claims of compliance. No consent screen grants
institutional ethics approval, and no passing integration test validates a study.

## Primary literature and concrete implications

[Peng et al.](https://arxiv.org/abs/2302.06590) report a controlled Copilot experiment
using a JavaScript HTTP-server task. Our inference: retain the task, population,
condition and outcome context; its productivity result does not validate a Python
debugging workload measure or transfer automatically to another population.

[Ziegler et al.](https://arxiv.org/abs/2205.06537) study Copilot user perceptions and
telemetry, finding an association with suggestion acceptance. Our inference:
keep perceived productivity and acceptance separate; neither alone establishes
causal productivity improvement or correctness. Templates should state their
required signals and applicability limits.

[Oelen et al.](https://arxiv.org/abs/2006.01747) describe aligning and comparing
research contributions in ORKG. Our inference: evidence mapping must preserve
study identity, method, context and source provenance, rather than treating
phrase frequency as support for a recommendation.

Next: verify full-text decision-bearing passages and obtain independent review
for #91; freeze expert-adjudicated cases for #95 before evaluating #92–98.
These initial notes are not a systematic review, a reviewed 20–30-study map, or
evidence that PHOENIX outperforms general assistants.
