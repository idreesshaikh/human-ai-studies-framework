# AGENTS.md — context for agents working in this repository

<!-- GENERATED FILE — do not edit by hand. Regenerate with
     `uv run python scripts/generate_agents_md.py`. Its inputs are the
     glossary, the SRS, a manifest snapshot, and CLAUDE.md's System
     invariants section. CI fails if this file drifts from its sources
     (FR-AGF-2). -->

This file orients an AI agent (Claude Code, a browser agent, or an SDK agent) working in this repository. Every section below is generated from a document of record, so it never drifts from the truth. For the live deployment's API, fetch `/.well-known/platform-manifest`.

## Platform

- **Name:** Framework for Conducting Human-AI Studies
- **Version:** 0.1.0
- **Capabilities:** analysis-recipes, conversation, corpus, curated-datasets, paper-matching, protocol-compilation, templates
- **Protocol schema versions:** [1, 2, 3] (consumers branch on version, never guess)
- **Event schema versions:** [2, 3, 4, 5]
- **Corpus:** 15000 papers (100 Tier A + 14900 Tier B); **templates:** 2

## System invariants (violating these breaks the science)

- **Join keys everywhere:** every data row of every leg carries
  `participantId`, `condition`, `sessionId`, timestamp, and a schema
  version. A data source that can't provide them doesn't ship (FR-INST-6).
- **Schema versioning:** any change to event shape/meaning bumps
  `SCHEMA_VERSION` (extension: `src/core/types.ts`) or `protocolVersion`.
  Consumers branch on version, never guess (FR-PROT-2, NFR-4).
- **Never interrupt the participant:** sensors/sinks/hooks are
  fire-and-forget; failures are swallowed, counted, reported once. Local
  JSONL is the source of truth; HTTP mirroring is best-effort; loss must be
  *detectable* via `seq` gaps (NFR-1, NFR-2).
- **Privacy by construction:** no raw code content, keystrokes, or clipboard
  text in any instrument — aggregates, shapes, salted hashes only. The two
  scoped exceptions (agent-conversation content, workspace snapshots) are
  governed by the protocol's consent-matched content policy (FR-ETH-2,
  FR-AGENT-5). The knowledge assistant may only ever see aggregates
  (FR-ETH-4) — enforce server-side, test with grep-the-output.
- **Port 8000** is the middleware contract all sensors assume (FR-ING-1).
- **Honest statistics:** exact tests, effect sizes, per-cell n; never bare
  p-values (NFR-8).
- **Participant data never enters git:** `.study-data/`, `*.sqlite3`,
  `results/`, `shadow.git/` are gitignored — keep it that way.

## Vocabulary

Use these terms in code identifiers, schema fields, and prose (`participant` not `user`, `condition` not `group`, `recipe` not `script`). Terminology disputes are settled by editing the glossary first.

- **Accepted chunk** — One contiguous agent-produced code contribution the participant accepted - the unit of engagement/comprehension analysis; its chunk reference joins probes, edit bursts, and agent turns (FR-INST-19). *(not: suggestion, diff)*
- **Adopt / adapt / build / reject** — The four reuse verdicts recorded per subsystem in `build-vs-adopt.md` (NFR-10).
- **Agent leg** — The fourth instrument family: structured capture of the AI agent's side - turns, tool calls, session metadata (FR-AGENT-1).
- **Agent participant** — An AI agent configuration (tool + model) enrolled as a study's data source, its sessions executed by the task harness; join keys and anonymized IDs apply exactly as for humans (FR-PROT-9). *(not: bot, subject system)*
- **Agent turn** — One prompt or response in the human-agent conversation, as a timestamped event (role, timing, sizes; text per content policy).
- **Amendment** — A post-ethics-approval protocol change: version bump + recorded rationale/approver; consent-relevant amendments require re-approval before new sessions (FR-CONV-4).
- **Capture config** — The versioned, protocol-derived set of enabled instruments/metrics an IDE applies at a session boundary (FR-INST-21).
- **Churn** — Lines added and then reworked or removed within the same session, from the snapshot series (FR-INST-17). *(not: rework, waste)*
- **Compilation** — The deterministic, LLM-free translation of accepted design moves into a validated protocol draft diff, applied only on approval (FR-CONV-3).
- **Comprehension probe** — A short, timeboxed, protocol-configured check (predict-output / locate-change) of the participant's understanding of an accepted chunk or injected defect, joined to its chunk (FR-INST-19). *(not: quiz, test)*
- **Condition** — An experimental arm a session runs under. Pilot values: `ai-assisted`, `unassisted`. *(not: group, treatment)*
- **Connection string** — The copy-safe `serverUrl#token` a participant pastes once to connect their IDE to a study.
- **Content policy** — The protocol-declared, consent-matched level of conversation text capture: `metadata-only` | `redacted` | `full` (FR-AGENT-5).
- **Corpus** — The platform's paper collection in provenance tiers: Tier A (hand-curated seeds with per-paper rationale), Tier B (pipeline-harvested, quality-gated, every row API-verifiable), plus per-study ingested papers (FR-LIT-8). *(not: library, database)*
- **Curated dataset** — A study dataset built from external sources (GitHub API, archives, replication packages) rather than live instrumented sessions, normalized into the one-timeline event schema with join keys and a provenance record (FR-CUR-1). *(not: mined dataset, secondary data)*
- **Dataset** — The middleware's joined, one-timeline export for a study - what recipes consume.
- **Design conversation** — The persistent per-study thread in which a study is elicited, designed, and evolved - the platform's primary design surface (FR-CONV-1). *(not: chat, wizard)*
- **Design move** — One platform-proposed protocol change carried as a structured, individually acceptable/rejectable object alongside a conversation turn (FR-CONV-1).
- **Elicitation record** — The stored design conversation - turns, moves, decisions, approvals - as the study's traceable requirements-elicitation artifact (FR-CONV-6).
- **Enrollment** — A participant's IDE joining a study by redeeming a pairing token.
- **Environment snapshot** — The session-start event recording tool/OS/extension/model versions for replication provenance (FR-INST-14).
- **Event** — One timestamped row of collected data conforming to the StudyEvent schema (`v, ts, mono, sessionId, participantId, condition, seq, type, payload`).
- **Facilitator** — The researcher operating a session (here: Idrees). *(not: experimenter, admin)*
- **Gate** — The validation checkpoint a study must pass to enter a phase (e.g. ethics approval artifact present before `data-collection`).
- **Grounding** — The citation set attached to a design move - paper refs, template IDs, SRS/glossary anchors; moves without it are labeled unsourced (FR-CONV-2). *(not: sources, evidence)*
- **Harvest** — The corpus-growth pipeline run: citation snowballing from Tier A seeds through the quality gate and ranking into Tier B (`scripts/corpus_harvest.py`, D36).
- **Heartbeat** — A lightweight periodic interaction signal used to classify active vs. idle time (WakaTime pattern, FR-INST-11).
- **Instrument** — A data-collecting component configured by the protocol (fatigue probes, stuck detection, behavioral telemetry, static metrics). *(not: sensor, tool)*
- **Join keys** — The fields present on every data row of every leg that make cross-leg joining possible: `participantId`, `condition`, `sessionId`, timestamp.
- **Knowledge assistant** — The Claude-powered Q&A over papers + protocol + aggregate dataset summaries, always citing sources (FR-LIT-4).
- **Leg** — One of the three instrument families sharing the study timeline: cognitive/self-report, behavioral, static code metrics.
- **Literature graph** — The interactive related-papers view built from citation-API edges around ingested papers (FR-LIT-2).
- **Living literature view** — The animated citation constellation doubling as the scoped-RAG surface: selection scopes retrieval, answers are chip-cited, gaps surface as halos (FR-LIT-10). *(not: graph view)*
- **Middleware** — The ingestion service unifying all legs into one queryable store. *(not: backend, server)*
- **Mining adapter** — A per-source importer producing curated-dataset rows behind the common normalizer contract (primary: GitHub API, FR-CUR-2).
- **Origin** — The provenance class of an edit burst: `human`, `ai`, `paste`, or `undo-redo` (FR-INST-10).
- **Pairing token** — The minted, single- or multi-use secret binding a study + participant + condition, delivered inside a connection string; redeemed by an IDE to enroll (FR-INST-20). *(not: session token)*
- **Paper** — An ingested publication (PDF / arXiv / DOI) with extracted metadata and text, linkable to protocol elements (FR-LIT-1/3).
- **Paper draft** — The generated Markdown/LaTeX write-up skeleton: methods from the frozen protocol, results from the report (FR-ANA-6).
- **Paper matching** — Surfacing corpus papers against the researcher's evolving idea with a stated match reason; accepted matches join the study's paper set with the reason preserved (FR-LIT-9).
- **Paper set** — The study's collection of ingested papers, keyed by canonical `paperRef` (`doi:`/`arxiv:`) so protocol `literature:` links join by construction; populated by upload/ID (FR-LIT-1). *(not: library, bibliography)*
- **Participant** — A data source enrolled in a study, identified only by an anonymized ID: a human (`P07`) or an agent participant (`A01`). *(Rev 2, 2026-07-17: agent participants added, FR-PROT-9; previously humans only.)* *(not: subject, user)*
- **Persistence** — The fraction of AI-origin inserted code surviving to session end (Ziegler et al.'s term; FR-INST-17). *(not: survival, retention)*
- **Phase** — A stage of the study lifecycle: `design → ethics → pilot → recruitment → data-collection → analysis → write-up`.
- **Platform manifest** — The machine-readable self-description of a deployment - capabilities, API surface, schemas, glossary, requirements - for AI agents operating the platform (FR-AGF-1).
- **Project** — A collaborative workspace owning studies, papers, datasets, and members; every study belongs to exactly one project (FR-PLAT-1). *(Redefined 2026-07-17: previously banned as a synonym of study; now the container concept.)*
- **Protocol** — The machine-readable (YAML) requirements specification of a study: RQs, conditions, participant plan, instruments, phases, analysis plan. *(“study-as-code”)*
- **RAG scope** — The researcher-selected subset of papers the assistant retrieves from for a given exchange - retrieval scoping, never an access-control mechanism (FR-LIT-10; FR-ETH-4 stays the boundary).
- **Recipe** — A pluggable analysis module declaring which RQs it answers and which data it requires, emitting tables, figures, and methods text.
- **Reliance loop** — The detectable sequence error-paste → agent turn → code-paste-back (FR-AGENT-3); a unit of agent dependence.
- **Report** — The per-study output of running all recipes in the protocol's analysis plan, organized by RQ.
- **Retrospective** — The post-study analysis of the framework's own operational log that proposes human-approved SRS/schema amendments (FR-META-2).
- **Review latency** — Time an AI suggestion was visible before the developer's accept/reject/dismiss decision (FR-INST-8).
- **Role** — A member's permission level within a project: `owner` | `researcher` | `viewer` (FR-PLAT-2). *(not: permission, group)*
- **Scroll coverage** — Fraction of an injected/changed code region whose lines appeared in the visible range before acceptance or save (FR-INST-9).
- **Session** — One continuous instrumented sitting of one participant under one condition; the unit that owns a JSONL file and a `sessionId`.
- **Session credential** — The short-lived bearer an IDE receives when it redeems a pairing token; authenticates ingest so the middleware can server-stamp join keys (FR-ING-7).
- **Snapshot** — One shadow-git commit of the task workspace (on save + timer), enabling metric time series (FR-INST-15).
- **Source adapter** — A per-agent-tool capture implementation behind the agent leg's common event contract (primary: Claude Code hooks + transcripts, D13).
- **Statistical plan** — The template-bound prescription of exact tests, effect sizes, corrections, and per-cell-n rules a design requires (FR-TPL-2, NFR-8). *(not: stats config)*
- **Study** — One complete empirical investigation, specified by exactly one protocol. *(not: experiment)*
- **Study designer** — The guided flow from research question to instantiated protocol: template selection, dataset-exists branch (curated vs. live), parameter form (FR-TPL-3). *(not: wizard)*
- **Study template** — A parameterized, citable encoding of a published study design (design type, conditions, instruments, measures, statistical plan) that instantiates into a valid protocol (FR-TPL-1). *(not: blueprint, preset)*
- **Task card** — An item in the platform's self-computing status view, auto-derived from an unsatisfied protocol condition (missing gate artifact, uncovered RQ, integrity warning); clears itself when the condition is satisfied (FR-DASH-7).
- **Task harness** — The per-task acceptance tests the framework runs to record outcome ground truth: pass/fail counts, time-to-first-green (FR-INST-16).
- **Traceability** — The maintained chain RQ → requirement → component → data element → recipe → claim, in both directions.
- **Validity-threats record** — The mandatory provenance companion of a curated dataset: sampling frame, inclusion criteria, known biases, heuristics used (FR-CUR-3).

## Requirements index

Every feature traces to a requirement ID. The full text lives in `requirements/srs.md`; this is the index.

- **FR-PROT-1** (M) A study SHALL be specified by exactly one YAML protocol validated against a published JSON Schema, covering metadata, RQs, conditions, participant plan, instruments+config, session plan, phases+gat… — _✅_
- **FR-PROT-2** (M) The protocol schema SHALL carry a `protocolVersion`, and validators SHALL branch on it rather than guess. — _✅_
- **FR-PROT-3** (M) The framework SHALL model the lifecycle `design → ethics → pilot → recruitment → data-collection → analysis → write-up`, where each phase transition is guarded by gates over required artifacts, and… — _✅_
- **FR-PROT-4** (M) Instrument configuration (e.g. `cognitiveOverlay.*` settings for a given participant/condition) SHALL be derivable from the protocol by command, with no hand-maintained side configuration. — _✅_
- **FR-PROT-5** (M) The protocol's analysis plan SHALL map each RQ to the recipes answering it; the framework SHALL be able to verify every RQ is covered. — _✅_
- **FR-PROT-7** (S) The framework SHALL export a replication kit: frozen protocol, schema+recipe versions, anonymized dataset, report. — _✅_
- **FR-PROT-8** (W) Support for arbitrary study types beyond agent–human developer studies. — _-_
- **FR-PROT-9** (S) The protocol schema SHALL support agent participants: studies whose sessions are harness-executed runs of an agent under test (participant = anonymized agent-configuration ID recording tool + model… — _✅_
- **FR-INST-1** (M) The cognitive leg SHALL sample fatigue via Likert micro-probes timed into typing pauses, with jitter and a quiet tail. — _✅ Cognitive Overlay v0.1_
- **FR-INST-2** (M) The cognitive leg SHALL detect stuck episodes (dwell / scroll-thrash) and prompt inline without stealing focus. — _✅_
- **FR-INST-3** (M) Sessions SHALL be governed by a pausable, crash-recoverable clock ending in a TLX-style debrief. — _✅_
- **FR-INST-4** (M) The static-metrics leg SHALL extract the full 9-metric cognitive-load matrix of `metrics/docs/static_code_metrics.md`: nesting depth penalty (exponential, tree-sitter), cognitive complexity (SonarQ… — _✅ (9/9)_
- **FR-INST-5** (M) The behavioral leg SHALL capture: tab/file focus switches (with workspace-relative paths), aggregated edit bursts (chars added/deleted, lines, duration, language), clipboard-paste events (size, lin… — _✅_
- **FR-INST-6** (M) Every data row of every leg SHALL carry the join keys (`participantId`, `condition`, `sessionId`, timestamp) and a schema version. — _✅ all four legs (overlay + behavioral, metrics, agent)_
- **FR-INST-7** (W) A JetBrains adapter reusing the IDE-agnostic core. — _-_
- **FR-INST-8** (M) The behavioral leg SHALL capture the AI-completion lifecycle: suggestion shown → accepted/rejected/dismissed, with review latency (time the suggestion was visible before the decision) and accepted-… — _✅ (blind spots in `extension/docs/adaptation-notes.md`)_
- **FR-INST-9** (M) The behavioral leg SHALL track visible ranges (debounced top/bottom line per visible editor) so analysis can compute scroll coverage - whether AI-injected or multi-file changes were actually scroll… — _✅_
- **FR-INST-10** (M) Every edit burst SHALL carry an origin classification: `human` (incremental typing), `ai` (completion-event correlated, or block insertion above size/speed thresholds), `paste`, or `undo-redo`. Thr… — _✅_
- **FR-INST-11** (S) The behavioral leg SHALL classify active vs. idle time via WakaTime-style heartbeats (interaction within a rolling window), so time-on-task excludes editor-open-but-absent periods. — _✅_
- **FR-INST-12** (S) Behavioral capture SHALL be filterable to protocol-declared languages/paths (pilot: Python files in the task workspace only). — _✅_
- **FR-INST-13** (S) All in-session prompts (fatigue probes, stuck prompts) SHALL render as translucent, glass-style in-editor surfaces layered over the code - never separate windows, screens, or apps; the participant'… — _✅: in-editor everywhere; debrief glass; fatigue probe stays native QuickPick (no stable overlay-webview API - constraint in `extension/docs/adaptation-notes.md`)_
- **FR-INST-14** (S) Session start SHALL record an environment snapshot event: VS Code version, extension versions, OS, agent tool + model identifier (AI condition), task ID. — _✅_
- **FR-INST-15** (S) The framework SHALL snapshot the task workspace over time (shadow git repo: commit on save + every N minutes, protocol-configurable) so static metrics can be computed as a time series and code evol… — _✅ (shadow-git snapshotter)_
- **FR-INST-16** (M) Each task SHALL ship acceptance tests; the framework SHALL run them at session end (and optionally on save) and record pass/fail counts and time-to-first-green as events. — _✅ (task harness)_
- **FR-INST-17** (S) The framework SHALL derive code-evolution / process metrics from the workspace-snapshot series (FR-INST-15) joined with origin-classified edit bursts (FR-INST-10): gross/net LOC added and deleted o… — _✅ (churn/persistence char-approximated, stated; line-level pending schema-v4 burst ranges)_
- **FR-INST-18** (C) The behavioral leg SHOULD capture a content-free IDE health stream: workspace diagnostics counts by severity (errors/warnings, debounced on change) and build/test invocations outside the harness, a… — _⬜_
- **FR-INST-19** (S) The cognitive leg SHALL support comprehension probes: short, timeboxed, protocol-configured checks (predict-output / locate-change) triggered when an agent-produced chunk is accepted and at mainten… — _⬜_
- **FR-INST-20** (M) The framework SHALL let a participant's IDE enroll into a study by redeeming one pairing token (a connection string encoding middleware URL + token) that resolves its identity (participantId, condi… — _⬜_
- **FR-INST-21** (M) The middleware SHALL serve a capture config derived deterministically from the protocol's instruments block; the IDE SHALL apply it at pair and at each session start behind a capture pre-flight; a… — _⬜_
- **FR-AGENT-1** (M) The framework SHALL capture agent interaction as structured events on the shared timeline (join keys + schema version like every leg): conversation turns (role, timing, text per content policy, cod… — _✅_
- **FR-AGENT-2** (M) The primary source adapter SHALL be Claude Code in the integrated terminal: real-time capture via Claude Code hooks POSTing to the middleware, plus post-session import of the on-disk transcript JSO… — _✅ (hooks + transcript importer, one normalizer)_
- **FR-AGENT-3** (S) The framework SHALL correlate agent events with editor events: an agent code block followed by a matching-size paste/injection within a window strengthens `origin: ai` (FR-INST-10); error-paste → a… — _✅ (correlate job: reliance loops + burst annotation)_
- **FR-AGENT-4** (C) Additional source adapters (Copilot Chat export import; generic markdown/JSON conversation import) MAY be added behind the same event contract. — _⬜_
- **FR-AGENT-5** (M) Conversation content policy SHALL be protocol-declared and consent-matched: `metadata-only` (sizes/timings/counts only - the default), `redacted` (text with string literals and identifiers ≥ N char… — _✅ (`redact.py` choke point; `metadata-only` default, grep-the-output tested)_
- **FR-ING-1** (M) The middleware SHALL listen on port 8000 (configurable) and accept event batches over HTTP matching the extension's existing HttpSink payload, unchanged. — _✅_
- **FR-ING-2** (M) Ingestion SHALL be idempotent on `(sessionId, seq)`: replayed batches create no duplicates. — _✅_
- **FR-ING-3** (M) The middleware SHALL detect and report per-session `seq` gaps. — _✅_
- **FR-ING-4** (M) The middleware SHALL export a study's joined one-timeline dataset (all legs) as JSON and CSV. — _✅_
- **FR-ING-5** (M) The middleware SHALL store uploaded files (session JSONL, consent artifacts, papers) indexed per study. — _✅_
- **FR-ING-6** (S) Ingested rows whose participant/condition are unknown to the protocol SHALL be stored and flagged, never dropped. — _✅_
- **FR-ING-7** (M) The middleware SHALL mint, list, and revoke pairing tokens (study-scoped, ethics-gated, role-gated) and verify them on redemption, issuing a short-lived session credential; credentialed ingest SHAL… — _⬜_
- **FR-DASH-1** (M) The platform SHALL show a study overview: protocol summary, RQs, planned-vs-collected sessions per condition. — _✅_
- **FR-DASH-2** (M) The platform SHALL render the lifecycle as a board whose current state is computed from gate artifacts, not hand-set. — _✅_
- **FR-DASH-3** (S) The platform SHALL show session status with recent events and seq-gap warnings. — _✅_
- **FR-DASH-4** (M) The platform SHALL render a per-session swimlane timeline interleaving events from all legs on one time axis. — _🔶 deferred (session status shows integrity; the swimlane view is not yet built)_
- **FR-DASH-5** (S) The platform SHALL show static-metric distributions split by condition. — _✅_
- **FR-DASH-6** (S) Every chart SHALL display which RQ/requirement it answers, sourced from the protocol's analysis plan. — _✅_
- **FR-DASH-7** (M) The platform SHALL surface study state as a self-computing status view derived from the protocol (unsatisfied gate artifacts, uncovered RQs, un-run recipes, integrity warnings), clearing itself whe… — _✅_
- **FR-DASH-8** (S) The platform SHALL host the knowledge views: the citation constellation (FR-LIT-2) and the grounded assistant (FR-LIT-4). — _✅_
- **FR-DASH-9** (S) The platform SHALL explain itself in plain language: hover tooltips for every requirement ID, research-question ID, and domain term it surfaces - tooltip text sourced from this SRS and the glossary… — _✅ tooltip/vocabulary layer built (the standalone guided tour was dropped; hero + demo onboard)_
- **FR-DASH-10** (S) The platform SHALL provide an enrollment surface in the study workspace: mint pairing tokens (batch/single, pick grain) as copy-links with live status (unredeemed/paired/streaming) and revoke, role… — _⬜_
- **FR-LIT-1** (M) The framework SHALL ingest papers by PDF upload and by arXiv ID / DOI, extracting metadata (title, authors, year, venue, abstract) and full text for the assistant. — _✅_
- **FR-LIT-2** (M) The framework SHALL build a related-papers graph around ingested papers via a citation API (Semantic Scholar: references, citations, recommendations), rendered as an interactive graph in the platfo… — _✅_
- **FR-LIT-3** (S) Papers SHALL be linkable to the protocol elements they justify (an RQ, an instrument, a metric, a recipe), and those links SHALL appear in the traceability views and the generated paper's related-w… — _✅_
- **FR-LIT-4** (M) The framework SHALL provide a knowledge assistant: natural-language Q&A over the study's papers, protocol, and dataset summaries, powered by the Claude API with tool use; every answer SHALL cite it… — _✅_
- **FR-LIT-6** (S) The knowledge view SHALL present the ingested papers as a visible, managed library: a list with add/remove, selection linked to the graph, and explicit progress feedback ("smart buffering") for any… — _✅_
- **FR-LIT-7** (C) The citation-graph provider SHALL be replaceable behind the existing fetch seam (Semantic Scholar today, self-paced to its 1 req/s budget; OpenAlex is the recorded candidate if S2's experience stay… — _⏳ seam exists (`cached_fetch`/`get_json`); swap not yet decided_
- **FR-LIT-8** (M*) The platform corpus SHALL be quality-first and uncapped in two provenance tiers — 1,000 papers is the floor, not the ceiling: Tier A (hand-curated, per-paper "why", `docs/papers/README.md`) and Tie… — _🔶 pipeline (uncapped + metric-rich scoring + `--propose-tier-a`) built; committed run pending re-harvest; importer pending_
- **FR-LIT-9** (M*) The platform SHALL match papers to the researcher's idea as the design conversation unfolds: candidate papers from the corpus (both tiers) surface as recommendation cards with a stated match reason… — _✅_
- **FR-LIT-10** (S) The study's knowledge SHALL be explorable as a living literature view: the citation graph animated as a responsive constellation that reacts to the conversation (papers glow when cited in a turn, d… — _⬜/17_
- **FR-ANA-1** (M) Analyses SHALL be recipes: pluggable modules declaring `id`, `answers` (RQ ids), `requires` (data elements), emitting tables, figures, and methods text. — _✅_
- **FR-ANA-2** (S) Recipe `requires` SHALL be validated against the protocol/dataset *before* data collection ends, failing loudly on missing data elements. — _✅_
- **FR-ANA-3** (M) Recipes covering all pilot RQs SHALL be built in: fatigue-by-condition, stuck-episodes, tlx-debrief, paste-behavior, code-quality-by-condition, ai-review-behavior (review latency, scroll coverage,… — _✅_
- **FR-ANA-4** (M) A runner SHALL execute the protocol's analysis plan and emit a per-study report organized by RQ. — _✅_
- **FR-ANA-5** (C) At least one published paper's analysis SHALL be implemented as a recipe, cited. — _✅_
- **FR-ANA-6** (M) The framework SHALL generate a paper draft from a completed study: Markdown + LaTeX skeleton with methods synthesized from the frozen protocol, results/figures/tables inserted from the recipe repor… — _✅ (`analysis paper`; golden-file + tectonic-compile tests)_
- **FR-META-1** (S) The framework SHALL log its own operational defects as structured findings - protocol validation failures, seq gaps, unknown-participant flags, gate blocks, recipe requires-failures, setup-friction… — _✅ (findings table + auto-scan for seq gaps + gate blocks; recipe requires-fails + `POST /findings`; platform finding cards)_
- **FR-META-2** (S) After each study, a retrospective SHALL analyze the operational log and the facilitator's findings and produce a proposed changelist to the SRS / protocol schema / instrument configs (Claude-assist… — _✅ (`analysis retrospective`; model-drafted proposal per D32, FR-ETH-4 prompt boundary grep-tested, offline template fallback, inert until human-applied)_
- **FR-META-3** (S) The platform SHALL run in-platform agents: scheduled, autonomous workflows hosted by the middleware that (a) scan for operational findings and integrity gaps on a cadence, (b) draft retrospective/p… — _⏳ specced (`docs/roadmap/18-evolution.md` extends the machinery); build not started_
- **FR-OPS-1** (S) The platform SHALL be deployable from its single container image (`middleware/Dockerfile` - one process serves API + platform, NFR-7) to (a) a free-tier container host as a public seeded demo, wher… — _🔶 manifests + pipeline built; account provisioning pending_
- **FR-OPS-2** (S) Releases SHALL be cut by pushing a git tag `vX.Y.Z` (release candidates: `vX.Y.Z-rc.N`): one pipeline re-runs the quality gates, builds the container image (pushed to GHCR tagged with the version),… — _🔶 pipeline built; first tagged release pending_
- **FR-OPS-3** (S) The extension SHALL be distributed on the VS Code Marketplace, published by the release pipeline on final tags, so a facilitator installs it by ID and configures it entirely via `protocol derive ov… — _🔶 pipeline built; Marketplace publisher account pending_
- **FR-OPS-4** (C) SonarQube SHALL remain on-demand in every deployment: locally the compose `--profile sonar`; in the cloud a deallocated VM that is started for analysis windows and deallocated after (workflow-dispa… — _🔶 workflow built; VM provisioning pending_
- **FR-OPS-5** (S) Platform sign-in SHALL be a pluggable auth provider behind one seam: `none` (local, default when no token is set), `token` (the existing bearer token, zero-config self-hosting - stays the default w… — _🔶 seam + token sign-in built (2026-07-16); Clerk client widget pending account provisioning_
- **FR-OPS-6** (C) The platform SHALL be hostable on a separate origin from the middleware for design iteration (D30 rev 2): the SPA takes an optional `VITE_API_BASE`, and the middleware SHALL allow cross-origin call… — _✅ built + tested_
- **FR-OPS-7** (S) Hosted deployments SHALL be profile-oriented: a signed-in Clerk identity (FR-OPS-5) becomes a user profile with per-user persisted preferences (theme, default assistant model, saved views) stored s… — _⏳ requires Clerk provisioning (FR-OPS-5's pending half) first_
- **FR-PLAT-1** (M) The platform SHALL model projects: a collaborative workspace owning studies, papers, datasets, and members; every study SHALL belong to exactly one project. — _✅_
- **FR-PLAT-2** (M) A signed-in identity (FR-OPS-5) SHALL resolve to project memberships with a role (`owner` | `researcher` | `viewer`); the owner manages membership; permissions SHALL be enforced server-side, never… — _✅_
- **FR-PLAT-3** (S) Members SHALL be invitable by email link, landing with the assigned role after sign-in. — _✅_
- **FR-PLAT-4** (S) The platform SHALL present a public hero page: what it does, entry to the live seeded demo, and sign-up - readable by a lay researcher per NFR-11. — _🔶 (built; server-seeded demo pending)_
- **FR-PLAT-5** (S) Self-hosted `none`/`token` deployments (FR-OPS-5) SHALL keep working project-free: a single implicit project, no sign-up, no regression for the one-facilitator laptop posture. — _✅_
- **FR-TPL-1** (M) The platform SHALL provide a study-template registry: parameterized, citable encodings of published study designs (design type, conditions, instruments, measures, session plan, analysis plan) that… — _🔶 (registry + statistical plans built; 2 of 4 seed templates ship)_
- **FR-TPL-2** (M) Every template SHALL bind a statistical plan: the exact tests, effect sizes, corrections, and per-cell-n rules its design requires (NFR-8 by construction), emitted into the instantiated protocol's… — _🔶_
- **FR-TPL-3** (S) The structured study designer SHALL be the synchronized review surface over the same protocol draft (the design conversation, FR-CONV-1, is the primary designer) - template parameters, the dataset-… — _⬜_
- **FR-TPL-4** (S) Templates SHALL cite their source papers by `paperRef` and surface in the knowledge layer (graph, assistant, FR-LIT-2/4), so "replicate this paper" is navigable from the literature view and every t… — _⬜_
- **FR-TPL-5** (C) Third-party templates MAY be contributed behind the same contract (schema validation + mandatory citation), reviewed before publication in the registry. — _⬜_
- **FR-CONV-1** (M) Every study SHALL have a persistent design conversation - the primary surface through which a study is elicited, designed, and evolved; platform proposals arrive as individually acceptable/rejectab… — _✅_
- **FR-CONV-2** (M) Every design move SHALL carry grounding (citations into the paper corpus, template registry, or SRS/glossary) or be visibly labeled unsourced; the assistant may only cite sources retrieved in that… — _✅_
- **FR-CONV-3** (M) Accepted design moves SHALL compile deterministically (no LLM in the compile step) into a protocol draft diff, validated on every compile, applied only on role-checked human approval; validation fa… — _✅_
- **FR-CONV-4** (S) Mid-study design/instrumentation changes SHALL route through phase-aware amendment rules: post-ethics amendments produce version bumps + amendment records; consent-relevant changes block new data-c… — _🔶 (engine + tests green; UI built + gated; live transport + browser evidence deferred)_
- **FR-CONV-5** (S) Researcher feedback SHALL be capturable in-conversation as structured findings feeding the retrospective and in-platform agents (FR-META-1/2/3) as inert, human-approved proposals; cross-project lea… — _🔶 (feedback→findings→inert proposal + aggregates-only shapes green; grep-the-output enforced; UI built + gated)_
- **FR-CONV-6** (M) The full conversation (turns, moves, decisions, compilations, approvals) SHALL be stored as the study's elicitation record - the traceable chain conversation turn → design move → grounding → protoc… — _✅_
- **FR-CUR-1** (M) The platform SHALL support studies whose data is a curated dataset: rows imported from external sources, normalized into the one-timeline event schema with the join keys (FR-INST-6) and a schema ve… — _✅_
- **FR-CUR-2** (S) A GitHub mining adapter SHALL import repositories, pull requests, commits, and issues via the GitHub API into curated-dataset rows - rate-limited, cached, resumable, degrading gracefully (NFR-4 ext… — _✅_
- **FR-CUR-3** (S) Every curated dataset SHALL carry a validity-threats record - sampling frame, inclusion criteria, known biases, heuristics used - surfaced in reports (FR-ANA-4) and paper drafts (FR-ANA-6). — _✅_
- **FR-CUR-4** (C) Published replication packages and research archives (e.g. DevGPT, arXiv:2309.03914) MAY be importable behind the same normalizer contract. — _⬜_
- **FR-AGF-1** (S) Deployments SHALL expose a platform manifest: machine-readable capabilities, API surface, event schemas, glossary, and requirements - extending the existing `/requirements` + `/glossary` endpoints… — _✅_
- **FR-AGF-2** (S) Repository and deployments SHALL ship agent context files (the AGENTS.md pattern) generated from the documents of record (SRS, glossary, protocol schema), never hand-maintained copies that drift. — _✅_
- **FR-AGF-3** (C) Platform surfaces MAY carry stable semantic annotations (`data-*` attributes) so browser-driving agents can operate the UI reliably. — _✅_
- **FR-ETH-1** (M) Ethics approval and per-participant consent SHALL be gate artifacts: `data-collection` is unreachable without them. — _✅+04_
- **FR-ETH-2** (M) Instruments SHALL NOT capture raw code content, raw keystrokes, or clipboard text; only aggregates, shapes, salted hashes, and workspace-relative paths. AI-lifecycle events record suggestion *sizes… — _✅ all legs comply (sizes/shapes/timings, salted in-memory hashes; agent-leg scoped exception via FR-AGENT-5)_
- **FR-ETH-3** (M) Participants SHALL appear in all stored data and outputs only as anonymized IDs; the ID↔identity mapping lives outside the framework. — _✅ by construction_
- **FR-ETH-4** (M) Knowledge-assistant calls to the LLM provider (the D32 provider, Mistral - the boundary is provider-independent) SHALL send only paper text, protocol content, and aggregate dataset summaries - neve… — _✅_
- **NFR-1** (M) Non-intrusiveness. No instrument may interrupt, block, or steal focus from the participant; sensors add no perceptible typing latency (fire-and-forget events to the local middleware, ActivityWatch-… — __
- **NFR-2** (M) Data integrity. Local JSONL is the source of truth; network mirroring is best-effort; loss must be detectable (seq gaps) even where not preventable. — __
- **NFR-3** (M) Portability. Scientifically meaningful logic (heuristics, schedules, schemas, survey wording) stays IDE-agnostic (`src/core` never imports `vscode`). — __
- **NFR-4** (M) Extensibility. All data schemas versioned; instruments and recipes plug in behind stable contracts without modifying existing legs. — __
- **NFR-5** (M) Privacy. Data minimization per FR-ETH-2/3/4; all study data at rest stays on facilitator-controlled machines; nothing leaves without an export action; the sole external calls are the citation API (… — __
- **NFR-6** (S) Reproducibility. Pinned dependency versions; recipes deterministic given a dataset; report and paper-draft regeneration bit-stable modulo timestamps. — __
- **NFR-7** (M) Operational simplicity. The full stack runs on one laptop, offline except FR-LIT/FR-META features, as `docker compose up` (middleware + platform; SonarQube optional profile). — __
- **NFR-8** (M) Analytical honesty. All statistical output reports exact tests, effect sizes, and per-cell n; no bare p-values; small-n framed as hypothesis-generating. — __
- **NFR-9** (M) Production readiness. One-command bring-up with health checks, a seeded demo mode (replayed sample study) so every view renders without live participants, structured logs, and a smoke-test script t… — __
- **NFR-10** (S) Build-vs-adopt discipline. Every subsystem records an adopt / adapt / build / reject decision with rationale in `requirements/build-vs-adopt.md` before implementation. — __
- **NFR-11** (S) Two-layer documentation (plain language outside, IDs inside). Requirement/decision IDs (`FR-*`, `NFR-*`, `D*`) live in `requirements/` and `docs/roadmap/` only. Every public-facing surface - README… — __
- **NFR-12** (M*) Experience quality. Every platform surface meets a product bar, specified testably in `specs/nfr-12-experience.md`: one token system shared by UI and charts (D34 shadcn/ui vendored; the dataviz pal… — __
