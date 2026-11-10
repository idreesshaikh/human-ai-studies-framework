# WSESE 2027 methodological readiness

WSESE is the quality target for this artifact. Software verification establishes
that the implemented contracts work under the tested conditions. A research
contribution also needs evidence that those contracts address a methodological
problem in a defined setting.

## Venue and contribution

Checked on 10 November 2026: the [official WSESE 2027 call](https://conf.researchr.org/home/icse-2027/wsese-2027)
emphasizes human–AI cooperation and welcomes work on operationalization, study
design, validity threats, replication and empirical-process automation.
It lists technical papers (6–8 pages), experience/work-in-progress reports
(4–6 pages), and vision/position papers (2–4 pages). Submission is
27 November 2026 AoE; the workshop is 26 April 2027. Recheck the official
instructions before submission rather than carrying forward earlier years'
formatting or review rules.

The candidate contribution is an executable connection between a reviewed
study design, declared measures, participant capture and reproducible analysis.
Frame the paper around the methodological failure it addresses and the
evidence for the proposed remedy. A working tool alone does not establish that
its advice improves study quality. Select the paper category to match the
evaluation actually completed.

## Claims and their evidence

| Claim or concern | Implemented evidence | Evidence still required for publication |
| --- | --- | --- |
| AI suggestions cannot silently become the recorded protocol | Review cards, explicit approval, deterministic compilation/validation, approval and streaming regressions | Independent review of generated plans and the researcher's correction burden |
| Outcomes correspond to declared capture | v6 typed measures, instrument definitions/hashes, producer contracts, cross-runtime survey tests | Evidence that each operationalization represents the intended construct in the target tasks/population |
| Planning respects the recorded design | Protocol hash, supported test/design checks, seeded numerical checks, explicit unsupported combinations | Justified effects/distributions, independent statistical review and sensitivity analysis for the actual study |
| Capture failures remain visible | Local JSONL, bounded retry queue, restart/outage regressions, sequence gaps and integrity flags | Calibration using independently observed sessions, including external tools and missing capture |
| Demo data cannot become a research finding by default | Explicit synthetic markers, excluded default exports/recipes/pilot estimates, dedicated example tests | Real consented data and documented provenance for empirical findings |
| Missing observations do not create artificial correlation pairs | Joint finite-row filtering before statistics and plotting; regressions with staggered missing values | Defensible missingness assumptions and independent units; repeated events require suitable aggregation or a repeated-measures model |
| Retrieval or model assistance improves design decisions | Frozen benchmark/evaluation interfaces, abstention and failure reporting | Independently labelled held-out cases, fair baselines, reviewer agreement and actual measured effects |
| Artifacts can be reproduced | Lockfiles, protocol/data hashes, deterministic exports, one-command verification with versioned logs | Archived immutable release and materials, exact model identifiers, redacted outputs and an independent reproduction |

## Evaluation needed before stronger claims

Define primary research questions and success criteria before inspecting
comparative results. A suitable evaluation can compare the framework with a
manual workflow or general assistant on the same frozen scenarios and tool
access. Record source-supported decisions, invalid protocols, assumptions,
abstentions, correction time, provider failures and end-to-end cost/latency.
Predefine the rubric and meaningful differences; do not equate fluent prose or
syntactic validity with sound methodology.

Have independent reviewers assess the source support, design, measurements,
analysis and validity threats. Record disagreements and adjudication. Keep
study/report families and paraphrased scenarios within a single split, and
calibrate thresholds without consulting the test set. A synthetic software
check and LLM-generated labels cannot replace independent judgments.

For participant evaluation, document recruitment, inclusion/exclusion,
consent/ethics approval, allocation, task equivalence, order/carryover,
tool/model versions, missingness, deviations and the analysis unit. Report
effect sizes and uncertainty, and address construct, internal, external and
conclusion validity. A control audit's `no-evidence` result cannot establish
that no AI assistance occurred. The experimental skill items are not a
validated skill instrument.

Archive the tested commit, protocol, task materials, instrument wording,
analysis commands, data dictionary, exclusion/approval history and verification
report. Share consent-compatible, de-identified data where permitted; explain
restrictions and provide synthetic reproduction fixtures where data cannot be
shared. Consult the [ICSE 2027 open-science policy](https://conf.researchr.org/track/icse-2027/icse-2027-icse-2027-open-science-policies)
and confirm which provisions the workshop applies.

The [evaluation guide](research-evaluation.md) defines the existing benchmark
and comparison process. The [planner methods](planner.md) document statistical
assumptions and unsupported combinations. The [demo rehearsal](demo-readiness.md)
documents reproducible engineering checks and their environmental limits.
Until independent evaluation is completed, describe this as a tested research
artifact with explicit methodological safeguards, and report evaluation gaps
as limitations.
