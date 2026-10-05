# Project report: evidence-linked developer studies

Repository-evidenced draft for #54/#58. This is not a submitted report, an
independent evaluation, or an attribution statement for individual team members.
Authors must review their contributions and the institution's submission rubric.

## Objective and scope

PHOENIX and TERN connect a researcher's protocol to participant assignment,
configured editor capture, integrity inspection, analysis and reproducible export.
The evidence extension links declared source passages and study constraints to
reviewable method choices. The scope is task-based human–AI software-development
studies; integration alone does not establish scientific recommendation quality.

## Design and implementation

The [architecture](architecture.md) separates views, authenticated controllers,
protocol/domain services and persistence. A versioned protocol remains executable
authority; a separate evidence map records study/publication identities, source
passages, review, applicability and measurement requirements.

Researchers describe a study or enter details manually. Model suggestions are
optional. They inspect evidence and alternatives, accept/reject decisions, compile
a preview and approve a validated protocol. Approval is not participation or
consent. Enrollment creates pairing credentials; TERN and optional producers emit
join-keyed events. Planning distinguishes accepted-decision previews from the
currently executable protocol. Replay and exports preserve captured-data limits.

## Repository evidence

- [#99](https://github.com/idreesshaikh/human-ai-studies-framework/pull/99): integrated
  core demo features, authoring/export fixes, capture and analysis contracts.
- [#100](https://github.com/idreesshaikh/human-ai-studies-framework/pull/100): configurable
  tested model route, with provider limitations documented.
- [#101](https://github.com/idreesshaikh/human-ai-studies-framework/pull/101): participant
  journey planning, enrollment usability and asynchronous-response hardening.
- [#103](https://github.com/idreesshaikh/human-ai-studies-framework/pull/103): delivered
  evidence/chat work to main and fixed scoped cleanup and rehearsal hygiene.
- [Evidence workflow](evidence-workflow.md), [replay](session-replay.md),
  [evaluation](research-evaluation.md), and their checked-in regression tests
  describe the newer implementation; cite its merged PR/version before submission.

## Evaluation and limitations

The merged #103 tree passed 823 software tests, 83% workspace coverage, frontend
checks, strict docs and desktop/mobile browser rehearsals. This is software
verification, not a human usability score, a real replication, or a measure of
research-design quality. Newer PRs must supply their own exact verification record.

The synthetic map and smoke benchmark exercise software boundaries only. A real
20–30-study independently reviewed map, expert-adjudicated held-out benchmark,
classifier comparison, general-assistant comparison and consented human pilot
remain separate research deliverables. No measured model superiority, effect
size, participant satisfaction or expert agreement is asserted here.

## Author and submission review

For #58–61 each named author must provide: assigned scope, personal contribution,
issue/PR/commit evidence, evaluation they actually performed, findings, limitations,
and a reviewed narrative. Do not infer authorship from an assignee or shared code.
For #54 obtain the required structure, length, citation style and marking rubric;
replace outstanding placeholders with verified evidence before final submission.
