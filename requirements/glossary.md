# Glossary - controlled vocabulary

Terms every document, schema field, and identifier in this repository must
use. One term per concept; synonyms listed only to ban them.

| Term            | Definition                                                                                                    |
| --------------- | ------------------------------------------------------------------------------------------------------------- |
| **Study**       | One complete empirical investigation, specified by exactly one protocol. *(not: experiment)*                  |
| **Project**     | A collaborative workspace owning studies, papers, datasets, and members; every study belongs to exactly one project (FR-PLAT-1). *(Redefined 2026-07-17: previously banned as a synonym of study; now the container concept.)* |
| **Role**        | A member's permission level within a project: `owner` \| `researcher` \| `viewer` (FR-PLAT-2). *(not: permission, group)* |
| **Protocol**    | The machine-readable (YAML) requirements specification of a study: RQs, conditions, participant plan, instruments, phases, analysis plan. *(“study-as-code”)* |
| **Condition**   | An experimental arm a session runs under. Pilot values: `ai-assisted`, `unassisted`. *(not: group, treatment)* |
| **Participant** | A data source enrolled in a study, identified only by an anonymized ID: a human (`P07`) or an agent participant (`A01`). *(Rev 2, 2026-07-17: agent participants added, FR-PROT-9; previously humans only.)* *(not: subject, user)* |
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
| **Task card**   | An item in the platform's self-computing status view, auto-derived from an unsatisfied protocol condition (missing gate artifact, uncovered RQ, integrity warning); clears itself when the condition is satisfied (FR-DASH-7). |
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
| **Study template** | A parameterized, citable encoding of a published study design (design type, conditions, instruments, measures, statistical plan) that instantiates into a valid protocol (FR-TPL-1). *(not: blueprint, preset)* |
| **Statistical plan** | The template-bound prescription of exact tests, effect sizes, corrections, and per-cell-n rules a design requires (FR-TPL-2, NFR-8). *(not: stats config)* |
| **Study designer** | The guided flow from research question to instantiated protocol: template selection, dataset-exists branch (curated vs. live), parameter form (FR-TPL-3). *(not: wizard)* |
| **Curated dataset** | A study dataset built from external sources (GitHub API, archives, replication packages) rather than live instrumented sessions, normalized into the one-timeline event schema with join keys and a provenance record (FR-CUR-1). *(not: mined dataset, secondary data)* |
| **Mining adapter** | A per-source importer producing curated-dataset rows behind the common normalizer contract (primary: GitHub API, FR-CUR-2). |
| **Validity-threats record** | The mandatory provenance companion of a curated dataset: sampling frame, inclusion criteria, known biases, heuristics used (FR-CUR-3). |
| **Platform manifest** | The machine-readable self-description of a deployment - capabilities, API surface, schemas, glossary, requirements - for AI agents operating the platform (FR-AGF-1). |
| **Design conversation** | The persistent per-study thread in which a study is elicited, designed, and evolved - the platform's primary design surface (FR-CONV-1). *(not: chat, wizard)* |
| **Design move** | One platform-proposed protocol change carried as a structured, individually acceptable/rejectable object alongside a conversation turn (FR-CONV-1). |
| **Grounding** | The citation set attached to a design move - paper refs, template IDs, SRS/glossary anchors; moves without it are labeled unsourced (FR-CONV-2). *(not: sources, evidence)* |
| **Compilation** | The deterministic, LLM-free translation of accepted design moves into a validated protocol draft diff, applied only on approval (FR-CONV-3). |
| **Amendment** | A post-ethics-approval protocol change: version bump + recorded rationale/approver; consent-relevant amendments require re-approval before new sessions (FR-CONV-4). |
| **Elicitation record** | The stored design conversation - turns, moves, decisions, approvals - as the study's traceable requirements-elicitation artifact (FR-CONV-6). |
| **Corpus** | The platform's paper collection in provenance tiers: **Tier A** (hand-curated seeds with per-paper rationale), **Tier B** (pipeline-harvested, quality-gated, every row API-verifiable), plus per-study ingested papers (FR-LIT-8). *(not: library, database)* |
| **Harvest** | The corpus-growth pipeline run: citation snowballing from Tier A seeds through the quality gate and ranking into Tier B (`scripts/corpus_harvest.py`, D36). |
| **Paper matching** | Surfacing corpus papers against the researcher's evolving idea with a stated match reason; accepted matches join the study's paper set with the reason preserved (FR-LIT-9). |
| **Living literature view** | The animated citation constellation doubling as the scoped-RAG surface: selection scopes retrieval, answers are chip-cited, gaps surface as halos (FR-LIT-10). *(not: graph view)* |
| **RAG scope** | The researcher-selected subset of papers the assistant retrieves from for a given exchange - retrieval scoping, never an access-control mechanism (FR-LIT-10; FR-ETH-4 stays the boundary). |
| **Agent participant** | An AI agent configuration (tool + model) enrolled as a study's data source, its sessions executed by the task harness; join keys and anonymized IDs apply exactly as for humans (FR-PROT-9). *(not: bot, subject system)* |
| **Accepted chunk** | One contiguous agent-produced code contribution the participant accepted - the unit of engagement/comprehension analysis; its chunk reference joins probes, edit bursts, and agent turns (FR-INST-19). *(not: suggestion, diff)* |
| **Comprehension probe** | A short, timeboxed, protocol-configured check (predict-output / locate-change) of the participant's understanding of an accepted chunk or injected defect, joined to its chunk (FR-INST-19). *(not: quiz, test)* |
| **Pairing token** | The minted, single- or multi-use secret binding a study + participant + condition, delivered inside a connection string; redeemed by an IDE to enroll (FR-INST-20). *(not: session token)* |
| **Connection string** | The copy-safe `serverUrl#token` a participant pastes once to connect their IDE to a study. |
| **Session credential** | The short-lived bearer an IDE receives when it redeems a pairing token; authenticates ingest so the middleware can server-stamp join keys (FR-ING-7). |
| **Capture config** | The versioned, protocol-derived set of enabled instruments/metrics an IDE applies at a session boundary (FR-INST-21). |
| **Enrollment** | A participant's IDE joining a study by redeeming a pairing token. |
