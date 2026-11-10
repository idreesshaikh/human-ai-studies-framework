# StudyLoop: connecting developer-study protocols to capture and analysis

Paper-shaped project report draft, prepared 10 November 2026. Implementation
and verification are grounded in repository evidence. The interview section
requires the original sources and analysis before submission. The team must
confirm authorship and institutional requirements.

## Abstract

Human–AI developer experiments require researchers to carry design choices
across study setup, participant instructions, instrumentation and analysis.
StudyLoop implements a protocol-driven workflow for a bounded class of these
experiments. Its researcher platform, PHOENIX, supports manual entry, templates
and optional model-assisted authoring through a shared compiler and explicit
approval path. Its VS Code extension, TERN, uses the approved configuration to
collect disclosed events and declared surveys. The service preserves instrument
versions, session integrity information and export provenance. A labelled
synthetic example illustrates the workflow, including incomplete capture and
the limits of control-arm signals. Automated checks exercise software behavior;
the example establishes no empirical effects or methodological superiority.
The final report will connect the implementation to the existing interview
study's verified findings and discuss unsupported designs, measurement
interpretation, capture blind spots and external-provider dependence.

## 1. Problem and scope

Preparing an experiment involves specifying outcomes, configuring the study,
collecting data and retaining enough information for analysis and review.
Changes or omissions between these steps can make recorded data difficult to
interpret. Research on TDD experiment reporting shows that measurement
procedures can affect outcomes and relevant details can be missing [1]. This
motivates explicit operational definitions and provenance, without establishing
the prevalence of the same problems in every human–AI experiment.

StudyLoop targets task-based human–AI software-development studies in a
supported editor environment. Its compiler supports bounded within- and
between-subjects comparisons. It does not certify construct validity, grant
ethics approval, recruit participants or replace statistical judgment.

The artifact connects approved study decisions, configured capture, integrity
inspection and portable analysis materials. Its usefulness should be assessed
against the needs documented in the existing interview study. Integration is
not presented as unprecedented or as proof of improved research quality.

## 2. Interview study and requirements

### Evidence status

The team has an existing interview study to consolidate. Source records, the
original guide, consent/use conditions, sample description and coding materials
have not yet been located in this repository. No participant count, quotation,
theme, saturation claim or usability score is inferred from code or from an
invitation to conduct additional interviews.

The [interview workflow](interview-study.md) prepares two or three additional
45-minute conversations and consolidation within eight hours including analysis.
It elicits existing practice before showing the example, keeping needs separate
from subsequent product reactions. It preserves the original analytic approach
rather than introducing a new effectiveness experiment.

### Required completion before submission

| Report element | Evidence to insert from the actual study |
| --- | --- |
| Purpose | Actual interview aim and research questions |
| Recruitment and sample | Inclusion, recruitment, relevant roles/experience, dates and final analyzed sample |
| Procedure | Guide versions, duration, what was shown, recording/notes and permitted use |
| Analysis | Method actually used, analyst roles, coding/memos and interpretation checks |
| Findings | Source-linked accounts, permitted verified quotations, contrasting cases and scope |
| Design consequences | Requirement → interview evidence → implemented behavior or deferred requirement |
| Limitations | Sampling, interviewer/demo influence, missing sources and analysis constraints |

Requirements must trace to supporting sources. A feature's presence does not
establish that participants requested it. Statements after a demonstration
cannot be reported as prior unmet needs without qualification. Findings that
challenge the tool should remain visible.

## 3. Tool design and implementation

### 3.1 One approved protocol

PHOENIX provides manual entry, templates and an optional design conversation.
They use the same study-plan compiler. Proposed changes remain reviewable;
researcher approval controls the executable protocol. The model cannot bypass
that approval path. Unsupported or malformed plans produce a refusal or a
correction request rather than silently becoming a run.

The compiler validates supported structure and declared contracts. This
mechanical guarantee is narrower than scientific appropriateness. The
[architecture](architecture.md) and [scope](scope.md) document the boundaries.

### 3.2 Capture and provenance

The approved protocol supplies assignment and disclosed instrument configuration.
TERN records supported events and surveys in VS Code. Local JSONL and retry
handling preserve delivery across tested failures. Optional producers, such as
a task harness, have separate execution requirements; declaring one does not
establish that it ran.

Typed measures identify an instrument, event fields and an analysis recipe.
Survey definitions carry wording, scale, scoring, version and hash information.
Analysis independently checks responses and instrument provenance. Legacy
string measures remain identifiable as untyped. These mechanisms expose
measurement choices but do not validate a new psychological instrument.

### 3.3 Planning, inspection and export

Recruitment calculations record assumptions against a protocol snapshot.
Supported recipes distinguish participant summaries from raw event counts.
Paired analyses have documented limits concerning period and carryover effects;
counterbalancing does not justify every analysis automatically [2].

Data inspection preserves incomplete sessions, sequence gaps and integrity
signals. Pilot and inclusion decisions retain reasons. Control-arm signals are
observations within the capture boundary: missing AI signals cannot prove that
no external AI tool was used.

Data bundles, design cards and replication kits retain configuration and analysis
materials. A separate evidence map records source passages, review status and
conditional applicability. Retrieved similarity and reported method use do not
establish validity. See [planner methods](planner.md) and
[evidence mapping](evidence-mapping.md).

## 4. Illustrative example

The example asks whether Copilot changes time to the first passing test on
bug-fixing tasks and reported workload. It contains a protocol, saved plan,
24 illustrative links and 25 simulated sessions. Deliberate imperfections
include incomplete capture, sequence gaps and a task mismatch. Every simulated
observation is marked synthetic.

The example uses real service routes to construct representative state. Default
research exports and analyses exclude its simulated observations; illustrative
enrollment links cannot pair an editor. It demonstrates behavior and error
states, with no claim about an observed Copilot effect.

The [walkthrough](demo-walkthrough.md) covers authoring, approval, planning,
capture scope, inspection and export. A disposable launcher separates rehearsal
from participant storage and removes provider dependence. Participant count and
session timing are presentation assumptions, not a justified real study design.

## 5. Software verification

Verification of commit `c15653e45a44cf673ed7711cc00e9757f27a7a76` on
10 November 2026 recorded:

| Check | Observed result |
| --- | --- |
| Python workspace | 1,156 tests passed; 86.77% coverage against the 79% floor |
| Metrics coverage | Passed the separate 95% floor |
| Extension | 238 tests passed; typecheck, lint and formatting passed |
| Production frontend/browser workflows | 642 checks across 174 theme/viewport states; no automated accessibility violations or page overflow |
| Documentation | Strict MkDocs build passed |

The initial extension gate encountered a missing local TypeScript executable.
Installing locked dependencies resolved this environment problem, and the
extension gate was rerun successfully. The record preserves the recovery.
These counts apply to that commit; subsequent changes need their own checks.

Checks include malformed model replies, interrupted chat, retry identity,
duplicate submission, Unicode input, capture recovery and synthetic-data
boundaries. A bounded live provider check produced compiler-valid drafts and
a valid refinement before rate limiting on a later request. This establishes
compatibility for that route and time, not model superiority.

These results concern tested behavior. They do not establish human usability,
advice quality, unobserved capture accuracy or empirical effectiveness. Browser
checks concern the tested Chromium configurations. The
[verification command](demo-readiness.md) records versions, source fingerprints,
exit codes and logs for subsequent builds.

## 6. Related work and positioning

Tea compiles declarative specifications into statistical tests [3]. Tisane
supports model authoring through conceptual and data relationships [4]. Gricea
represents conversational-AI studies as inspectable executable artifacts [5].
VibeJam provides an instrumented coding-agent study environment [6]. These are
close predecessors; StudyLoop should not claim to invent executable experiments,
statistical guidance or instrumented human–AI platforms.

The report should explain its supported developer-study workflow, the choices
made for target users and the requirements supported by the consolidated
interviews. Comparing scope and trade-offs is more defensible than asserting
superiority without comparison. Empirical standards provide guidance for
describing and evaluating an engineering artifact [7].

## 7. Limitations and future work

Supported study families and recipes are bounded. Task-test success is a
particular outcome, not universal correctness. Questionnaire interpretation
depends on wording, scoring, context and supporting evidence. External tools
and activity outside the editor create blind spots. Provider availability and
changing model aliases limit reproducibility of assisted authoring.

Interview limitations must be completed from the actual procedure. A small
purposive sample and demo reactions cannot establish population prevalence or
causal improvements in researcher performance. Synthetic sessions cannot supply
missing empirical evidence.

Future work could assess outcome-specific rehearsal checks, reviewed evidence
mappings or comparative authoring workflows. These are extensions for stronger
claims, not unfinished delivery requirements. Current work remains cleanup,
interview consolidation, documentation and the illustrative demonstration.

## 8. Conclusion

StudyLoop implements a protocol-driven path through authoring, participant
capture, inspection and export. Engineering evidence and an illustrative example
make that path inspectable. The completed report must ground researcher needs
in the interview study and preserve the boundaries of what the tool establishes.

## References

1. [Relevant information in TDD experiment reporting](https://arxiv.org/abs/2406.06405).
2. [Crossover Designs in Software Engineering Experiments: Review of the State of Analysis](https://arxiv.org/abs/2408.07594).
3. [Tea: A High-level Language and Runtime System for Automating Statistical Analysis](https://idl.uw.edu/papers/tea).
4. [Tisane: Authoring Statistical Models via Formal Reasoning from Conceptual and Data Relationships](https://arxiv.org/abs/2201.02705).
5. [Gricea: An Open Science Platform for Conversational AI Research](https://arxiv.org/abs/2609.22039). Preprint.
6. [VibeJam: A User Study Platform for Web Development with Agents](https://arxiv.org/abs/2608.29889).
7. [ACM SIGSOFT Empirical Standards](https://www2.sigsoft.org/EmpiricalStandards/docs/standards).

Before submission, complete bibliographic metadata, check publication versions,
confirm contributions and follow the institutional rubric. Select any workshop
category and claim scope with the supervisor using [WSESE guidance](wsese-2027-readiness.md).
