<!-- trace: RQ-F1 / protocol.study / FR-PROT-1 -->
# AI assistance and developer cognitive load: a within-subjects pilot

**Idrees Razak; Project Supervisor**

## Abstract

<!-- trace: RQ-F1 / protocol.study / FR-PROT-1 -->
We report a within-subjects study of ai-assisted, unassisted with 0 of a planned 6 participants. `TODO: verify` State the headline effect size and exact test per research question from the Results section.

## Introduction and research questions

<!-- trace: RQ-P1 -->
**RQ-P1.** How does AI assistance affect self-reported cognitive load (fatigue probes, stuck episodes, TLX debrief)?

<!-- trace: RQ-P2 -->
**RQ-P2.** How does AI assistance affect the static cognitive-load profile of the code produced (9-metric matrix over workspace snapshots)?

<!-- trace: RQ-P3 -->
**RQ-P3.** How does AI assistance change working behavior - pasting, file switching, edit provenance, active vs idle time?

<!-- trace: RQ-P4 -->
**RQ-P4.** How do developers review AI-generated code before accepting it (review latency, scroll coverage, accept rate by suggestion size)?

<!-- trace: RQ-P5 -->
**RQ-P5.** How does the conversation with the agent unfold over a session - turn cadence, tool-call mix, reliance loops - and how does it relate to outcomes?

## Related work

### Grounding RQ-P3

<!-- trace: FR-LIT-3 / arxiv:2302.06590 -->
arxiv:2302.06590 motivates RQ-P3, RQ-P4. [@arxiv_2302_06590] `TODO: summarise contribution and contrast.`

<!-- trace: FR-LIT-3 / doi:10.1109/TSE.2017.2656886 -->
doi:10.1109/TSE.2017.2656886 motivates RQ-P3. [@doi_10_1109_tse_2017_2656886] `TODO: summarise contribution and contrast.`

### Grounding RQ-P4

<!-- trace: FR-LIT-3 / arxiv:2205.06537 -->
arxiv:2205.06537 motivates RQ-P4. [@arxiv_2205_06537] `TODO: summarise contribution and contrast.`

## Methodology

<!-- trace: FR-PROT-1 / participants -->
We plan 6 participants in a within-subjects, counterbalanced design across the conditions ai-assisted, unassisted.

<!-- trace: FR-PROT-1 / session -->
Each session lasts 45 minutes. Two matched Python maintenance tasks (one per condition, order counterbalanced with condition pairing per the runbook's Latin square): Task A "expenses" and Task B "logbook" (study/pilot/tasks/), each a small existing codebase with two seeded defects and one feature request, shipped with acceptance tests providing outcome ground truth (FR-INST-16, harness lands with MP-12). In ai-assisted sessions the participant uses Claude Code in the integrated terminal; in unassisted sessions AI tooling is disabled.

### Instruments

<!-- trace: FR-INST-1 / FR-INST-2 / cognitiveOverlay -->
The Cognitive Overlay samples fatigue every 15 minutes (after a 4-second typing pause) and detects stuck episodes after 90 seconds of inactivity (FR-INST-1/2).

<!-- trace: FR-AGENT-2 / FR-AGENT-5 / agentCapture -->
In the AI condition the agent interaction is captured via claude-code under a metadata-only content policy (FR-AGENT-2/5).

### Static code metrics (cognitive-load-9)

<!-- trace: FR-INST-4 / metrics -->
| Metric | Definition | Source |
| --- | --- | --- |
| Nesting penalty | weighted count of nested control structures | [@nejmeh1988] |
| Cognitive complexity | SonarSource cognitive-complexity score | [@campbell2018] |
| Parameter count | arity vs Miller's 7+/-2 working-memory bound | [@miller1956] |
| Halstead effort | Halstead's effort measure over operators/operands | [@halstead1977] |
| Scope distance | mean lines between a name's definition and use | [@nejmeh1988] |
| Indentation variance | variance of leading-whitespace depth per file | [@hindle2008] |
| Line width | mean/bounded source line length | [@hindle2008] |
| Identifier length | mean identifier character length | [@lawrie2006] |
| Comment ratio | comment lines / source lines | [@nejmeh1988] |

<!-- trace: FR-ETH-1 / FR-ETH-2 / ethics -->
Ethics reference: UoM CS ethics application (in preparation; gate blocks data-collection). Consent is matched to the declared content policy (FR-ETH-2/FR-AGENT-5).

## Results

### RQ-P1

<!-- trace: RQ-P1 / fatigue-by-condition / RQ-P1 -->
**fatigue-by-condition.** `TODO: recipe did not run (missing data or error).`

<!-- trace: RQ-P1 / stuck-episodes / RQ-P1 -->
**stuck-episodes.** `TODO: recipe did not run (missing data or error).`

<!-- trace: RQ-P1 / tlx-debrief / RQ-P1 -->
**tlx-debrief.** `TODO: recipe did not run (missing data or error).`

### RQ-P2

<!-- trace: RQ-P2 / code-quality-by-condition / RQ-P2 -->
**code-quality-by-condition.** `TODO: recipe did not run (missing data or error).`

### RQ-P3

<!-- trace: RQ-P3 / paste-behavior / RQ-P3 -->
**paste-behavior.** `TODO: recipe did not run (missing data or error).`

<!-- trace: RQ-P3 / meyer-fragmentation / RQ-P3 -->
**meyer-fragmentation.** `TODO: recipe did not run (missing data or error).`

### RQ-P4

<!-- trace: RQ-P4 / ai-review-behavior / RQ-P4 -->
**ai-review-behavior.** `TODO: recipe did not run (missing data or error).`

<!-- trace: RQ-P4 / ziegler-acceptance-rate / RQ-P4 -->
**ziegler-acceptance-rate.** `TODO: recipe did not run (missing data or error).`

### RQ-P5

<!-- trace: RQ-P5 / agent-interaction-dynamics / RQ-P5 -->
**agent-interaction-dynamics.** `TODO: recipe did not run (missing data or error).`

<!-- trace: RQ-P5 / task-outcome-by-condition / RQ-P1,RQ-P2,RQ-P3,RQ-P4,RQ-P5 -->
**task-outcome-by-condition.** `TODO: recipe did not run (missing data or error).`

## Threats to validity

<!-- trace: threats / scope-discipline -->
**Origin-classification blind spots.** edit-provenance is a debounced heuristic (typed vs AI-injected vs pasted); rapid interleaving can misattribute a burst - the agent-leg correlation strengthens but does not eliminate this (FR-INST-10, FR-AGENT-3).

<!-- trace: threats / scope-discipline -->
**Small-n framing.** pilot samples are hypothesis-generating; exact nonparametric tests and effect sizes are reported with per-cell n, and no claim rests on a bare p-value (NFR-8).

<!-- trace: threats / scope-discipline -->
**Single-IDE, single-agent scope.** capture is VS Code + Claude Code; generality to other editors/agents is by design, not demonstration (scope discipline; FR-AGENT-4 extension point).

<!-- trace: threats / scope-discipline -->
**Self-report instruments.** fatigue and stuck probes are Likert self-reports subject to the usual response biases.

