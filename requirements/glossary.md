# Glossary - controlled vocabulary

Terms every document, schema field, and identifier in this repository must
use. One term per concept; synonyms listed only to ban them.

| Term            | Definition                                                                                                    |
| --------------- | ------------------------------------------------------------------------------------------------------------- |
| **Study**       | One complete empirical investigation, specified by exactly one protocol. *(not: experiment, project)*         |
| **Protocol**    | The machine-readable (YAML) requirements specification of a study: RQs, conditions, participant plan, instruments, phases, analysis plan. *(“study-as-code”)* |
| **Condition**   | An experimental arm a session runs under. Pilot values: `ai-assisted`, `unassisted`. *(not: group, treatment)* |
| **Participant** | A human data source, identified only by an anonymized ID (`P07`). *(not: subject, user)*                      |
| **Session**     | One continuous instrumented sitting of one participant under one condition; the unit that owns a JSONL file and a `sessionId`. |
| **Instrument**  | A data-collecting component configured by the protocol (fatigue probes, stuck detection, behavioral telemetry, static metrics). *(not: sensor, tool)* |
| **Leg**         | One of the three instrument families sharing the study timeline: cognitive/self-report, behavioral, static code metrics. |
| **Event**       | One timestamped row of collected data conforming to the StudyEvent schema (`v, ts, mono, sessionId, participantId, condition, seq, type, payload`). |
| **Join keys**   | The fields present on every data row of every leg that make cross-leg joining possible: `participantId`, `condition`, `sessionId`, timestamp. |
| **Phase**       | A stage of the study lifecycle: `design → ethics → pilot → recruitment → data-collection → analysis → write-up`. |
| **Gate**        | The validation checkpoint a study must pass to enter a phase (e.g. ethics approval artifact present before `data-collection`). |
| **Middleware**  | The ingestion service unifying all legs into one queryable store. *(not: backend, server)*                    |
| **Dataset**     | The middleware's joined, one-timeline export for a study - what recipes consume.                              |
| **Recipe**      | A pluggable analysis module declaring which RQs it answers and which data it requires, emitting tables, figures, and methods text. |
| **Report**      | The per-study output of running all recipes in the protocol's analysis plan, organized by RQ.                 |
| **Traceability**| The maintained chain RQ → requirement → component → data element → recipe → claim, in both directions.        |
| **Facilitator** | The researcher operating a session (here: Idrees). *(not: experimenter, admin)*                               |
| **Origin**      | The provenance class of an edit burst: `human`, `ai`, `paste`, or `undo-redo` (FR-INST-10).                    |
| **Review latency** | Time an AI suggestion was visible before the developer's accept/reject/dismiss decision (FR-INST-8).       |
| **Scroll coverage** | Fraction of an injected/changed code region whose lines appeared in the visible range before acceptance or save (FR-INST-9). |
| **Heartbeat**   | A lightweight periodic interaction signal used to classify active vs. idle time (WakaTime pattern, FR-INST-11). |
| **Task card**   | A dashboard project-manager item auto-derived from an unsatisfied protocol condition (missing gate artifact, uncovered RQ, integrity warning) or added manually; clears itself when the condition is satisfied (FR-DASH-7). |
| **Paper** *(artifact)* | An ingested publication (PDF / arXiv / DOI) with extracted metadata and text, linkable to protocol elements (FR-LIT-1/3). |
| **Paper set**   | The study's collection of ingested papers, keyed by canonical `paperRef` (`doi:`/`arxiv:`) so protocol `literature:` links join by construction; populated by upload/ID (FR-LIT-1). *(not: library, bibliography)* |
| **Literature graph** | The interactive related-papers view built from citation-API edges around ingested papers (FR-LIT-2).      |
| **Knowledge assistant** | The Claude-powered Q&A over papers + protocol + aggregate dataset summaries, always citing sources (FR-LIT-4). |
| **Paper draft** | The generated Markdown/LaTeX write-up skeleton: methods from the frozen protocol, results from the report (FR-ANA-6). |
| **Retrospective** | The post-study analysis of the framework's own operational log that proposes human-approved SRS/schema amendments (FR-META-2). |
| **Adopt / adapt / build / reject** | The four reuse verdicts recorded per subsystem in `build-vs-adopt.md` (NFR-10).             |
| **Agent leg**   | The fourth instrument family: structured capture of the AI agent's side - turns, tool calls, session metadata (FR-AGENT-1). |
| **Agent turn**  | One prompt or response in the human-agent conversation, as a timestamped event (role, timing, sizes; text per content policy). |
| **Source adapter** | A per-agent-tool capture implementation behind the agent leg's common event contract (primary: Claude Code hooks + transcripts, D13). |
| **Content policy** | The protocol-declared, consent-matched level of conversation text capture: `metadata-only` \| `redacted` \| `full` (FR-AGENT-5). |
| **Reliance loop** | The detectable sequence error-paste → agent turn → code-paste-back (FR-AGENT-3); a unit of agent dependence. |
| **Churn**       | Lines added and then reworked or removed within the same session, from the snapshot series (FR-INST-17). *(not: rework, waste)* |
| **Persistence** | The fraction of AI-origin inserted code surviving to session end (Ziegler et al.'s term; FR-INST-17). *(not: survival, retention)* |
| **Snapshot**    | One shadow-git commit of the task workspace (on save + timer), enabling metric time series (FR-INST-15). |
| **Task harness** | The per-task acceptance tests the framework runs to record outcome ground truth: pass/fail counts, time-to-first-green (FR-INST-16). |
| **Environment snapshot** | The session-start event recording tool/OS/extension/model versions for replication provenance (FR-INST-14). |
