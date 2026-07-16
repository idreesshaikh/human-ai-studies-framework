# Software Requirements Specification

Requirements for the **Framework for Conducting Human-AI Studies**
(`roadmap/00-VISION.md`). IDs are stable; MoSCoW priorities define the
sprint cut line: **Must = the one-week production slice. Should = built if
the day has slack, else immediately after. Could = stretch. Won't = the
multi-year vision, deliberately deferred and argued as such.**
Terms per `glossary.md`; traceability in `traceability.md`; reuse decisions
in `build-vs-adopt.md`. Elicitation sources: supervisor (dashboard-as-
project-manager), `extension/docs/developer_behavior_capture.md` (behavioral leg,
reference plugins), `metrics/docs/static_code_metrics.md` (9-metric matrix).

Status key: ✅ built · 🔶 partial · ⬜ open · - deliberately not built.

---

## FR-PROT - Protocol subsystem (study-as-code)

| ID        | P | Requirement | Rationale | Status |
| --------- | - | ----------- | --------- | ------ |
| FR-PROT-1 | M | A study SHALL be specified by exactly one YAML protocol validated against a published JSON Schema, covering metadata, RQs, conditions, participant plan, instruments+config, session plan, phases+gates, analysis plan, and literature links. | RQ-F1: the protocol *is* the study's requirements spec. | ✅ MP-02 |
| FR-PROT-2 | M | The protocol schema SHALL carry a `protocolVersion`, and validators SHALL branch on it rather than guess. | S6: old studies stay readable; change management. | ✅ MP-02 |
| FR-PROT-3 | M | The framework SHALL model the lifecycle `design → ethics → pilot → recruitment → data-collection → analysis → write-up`, where each phase transition is guarded by gates over required artifacts, and SHALL report current phase and missing artifacts on demand. | S1 always knows where they are; S3's approval is enforced, not remembered. | ✅ MP-02 |
| FR-PROT-4 | M | Instrument configuration (e.g. `cognitiveOverlay.*` settings for a given participant/condition) SHALL be derivable from the protocol by command, with no hand-maintained side configuration. | RQ-F1 falsifier: any needed side-channel config is a specification defect. | ✅ MP-02 |
| FR-PROT-5 | M | The protocol's analysis plan SHALL map each RQ to the recipes answering it; the framework SHALL be able to verify every RQ is covered. | RQ-F2: traceability by construction. | ✅ MP-02 |
| ~~FR-PROT-6~~ | - | ~~The protocol MAY attach literature artifacts.~~ *Superseded 2026-07-11 by FR-LIT-1/FR-LIT-3 (knowledge layer promoted to a subsystem).* | - | - |
| FR-PROT-7 | S | The framework SHALL export a replication kit: frozen protocol, schema+recipe versions, anonymized dataset, report. | RQ-F3; S5. | ✅ |
| FR-PROT-8 | W | Support for arbitrary study types beyond agent–human developer studies. | Generality by schema design only, this project. | - |

## FR-INST - Instrumentation (the three legs)

| ID        | P | Requirement | Rationale | Status |
| --------- | - | ----------- | --------- | ------ |
| FR-INST-1 | M | The cognitive leg SHALL sample fatigue via Likert micro-probes timed into typing pauses, with jitter and a quiet tail. | RQ-P1; NFR-1. | ✅ Cognitive Overlay v0.1 |
| FR-INST-2 | M | The cognitive leg SHALL detect stuck episodes (dwell / scroll-thrash) and prompt inline without stealing focus. | RQ-P1; NFR-1. | ✅ |
| FR-INST-3 | M | Sessions SHALL be governed by a pausable, crash-recoverable clock ending in a TLX-style debrief. | RQ-P1; session integrity. | ✅ |
| FR-INST-4 | M | The static-metrics leg SHALL extract the full 9-metric cognitive-load matrix of `metrics/docs/static_code_metrics.md`: nesting depth penalty (exponential, tree-sitter), cognitive complexity (SonarQube API, stub-degradable), parameter count (Miller's Law rationale), Halstead mental effort (Radon), variable scope distance, indentation variance, line-width bounds, average identifier length, comment-to-code ratio - per-function and per-file as applicable. | RQ-P2; each metric maps to a working-memory / visual-friction construct. | ✅ MP-03 (9/9) |
| FR-INST-5 | M | The behavioral leg SHALL capture: tab/file focus switches (with workspace-relative paths), aggregated edit bursts (chars added/deleted, lines, duration, language), clipboard-paste events (size, line count, internal-copy latency - never content), file saves, and window/terminal focus. | RQ-P3; `extension/docs/developer_behavior_capture.md`; C1 resolution. | ✅ MP-05 |
| FR-INST-6 | M | Every data row of every leg SHALL carry the join keys (`participantId`, `condition`, `sessionId`, timestamp) and a schema version. | The one-timeline invariant; RQ-F1. | 🔶 overlay ✅ (incl. behavioral leg, MP-05), metrics ✅; agent leg MP-12 |
| FR-INST-7 | W | A JetBrains adapter reusing the IDE-agnostic core. | NFR-3 makes it possible; thesis argues it, doesn't build it. | - |
| FR-INST-8 | M | The behavioral leg SHALL capture the AI-completion lifecycle: suggestion shown → accepted/rejected/dismissed, with **review latency** (time the suggestion was visible before the decision) and accepted-suggestion size. | RQ-P4 (how developers review AI code before accepting) - the Tako-informed differentiator. | ✅ MP-05 (blind spots in `extension/docs/adaptation-notes.md`) |
| FR-INST-9 | M | The behavioral leg SHALL track visible ranges (debounced top/bottom line per visible editor) so analysis can compute **scroll coverage** - whether AI-injected or multi-file changes were actually scrolled through before acceptance/save. | RQ-P4; `extension/docs/developer_behavior_capture.md` §Visual Viewing Ranges. | ✅ MP-05 |
| FR-INST-10 | M | Every edit burst SHALL carry an **origin classification**: `human` (incremental typing), `ai` (completion-event correlated, or block insertion above size/speed thresholds), `paste`, or `undo-redo`. Thresholds SHALL be protocol-configurable and the classification heuristic documented. | RQ-P3/P4: "if a massive block appears in 1 ms it was injected" - made rigorous. | ✅ MP-05 |
| FR-INST-11 | S | The behavioral leg SHALL classify active vs. idle time via WakaTime-style heartbeats (interaction within a rolling window), so time-on-task excludes editor-open-but-absent periods. | Honest denominators for all rate metrics. | ✅ MP-05 |
| FR-INST-12 | S | Behavioral capture SHALL be filterable to protocol-declared languages/paths (pilot: Python files in the task workspace only). | Data minimization (S2/S3); WakaTime language-filter pattern. | ✅ MP-05 |
| FR-INST-13 | S | All in-session prompts (fatigue probes, stuck prompts) SHALL render as translucent, glass-style in-editor surfaces layered over the code - never separate windows, screens, or apps; the participant's eyes stay on their work. | S2/NFR-1: cognitive-load sampling that doesn't itself add load. Debrief webview is already glassmorphic; probes upgrade from QuickPick where the API allows. | ✅ MP-05: in-editor everywhere; debrief glass; fatigue probe stays native QuickPick (no stable overlay-webview API - constraint in `extension/docs/adaptation-notes.md`) |
| FR-INST-14 | S | Session start SHALL record an environment snapshot event: VS Code version, extension versions, OS, agent tool + model identifier (AI condition), task ID. | S5: replication dies without environment provenance. | ✅ MP-05 |
| FR-INST-15 | S | The framework SHALL snapshot the task workspace over time (shadow git repo: commit on save + every N minutes, protocol-configurable) so static metrics can be computed as a **time series** and code evolution reconstructed, not just the final state. | RQ-P2 as trajectory; joins metrics leg to the timeline properly. | ⬜ |
| FR-INST-16 | M | Each task SHALL ship acceptance tests; the framework SHALL run them at session end (and optionally on save) and record pass/fail counts and time-to-first-green as events. | Outcome ground truth: without correctness, RQ-P2 measures style, not success. | ⬜ |
| FR-INST-17 | S | The framework SHALL derive **code-evolution / process metrics** from the workspace-snapshot series (FR-INST-15) joined with origin-classified edit bursts (FR-INST-10): gross/net LOC added and deleted over the session, within-session **churn** (lines added then reworked or removed before session end), and **AI-code persistence** (fraction of AI-origin insertions surviving to session end); and SHALL record the participant's own VCS activity in the task repo as content-free `git_commit` events (hash, files changed, insertions, deletions, timing - never message text). *(Added 2026-07-12: elicitation from the metric-coverage review, `requirements/metric-coverage.md`.)* | Commits, LOC deltas, and churn are the most-reported telemetry metrics in LLM-assistant studies (SLR arXiv:2507.03156); persistence is Ziegler et al.'s (arXiv:2205.06537) second headline measure. Without them the code leg misses the literature's basic units, and the framework can't host those papers as recipes. | ⬜ |
| FR-INST-18 | C | The behavioral leg SHOULD capture a content-free **IDE health stream**: workspace diagnostics counts by severity (errors/warnings, debounced on change) and build/test invocations outside the harness, as timeline events. *(Added 2026-07-12, same elicitation.)* | An error-count trajectory is an objective struggle proxy that joins fatigue probes and stuck episodes on the shared timeline; lab studies use it as a difficulty signal. Cheap via the VS Code diagnostics API; schema-v4 candidate. | ⬜ |

## FR-AGENT - Agent interaction leg (the fourth instrument leg)

| ID         | P | Requirement | Rationale | Status |
| ---------- | - | ----------- | --------- | ------ |
| FR-AGENT-1 | M | The framework SHALL capture agent interaction as structured events on the shared timeline (join keys + schema version like every leg): conversation turns (role, timing, text per content policy, code-block count/size/language), tool calls (name, duration, success), and session metadata (agent tool, model ID, token counts). | The agent is a study subject too: RQ-P5; feeds the dashboard like every other leg. | ⬜ |
| FR-AGENT-2 | M | The primary source adapter SHALL be Claude Code in the integrated terminal: real-time capture via Claude Code hooks POSTing to the middleware, plus post-session import of the on-disk transcript JSONL as the completeness backstop (hooks may miss what transcripts keep). The pilot's `ai-assisted` condition standardizes on this setup. | Only agent tool with lossless, machine-readable capture; decision D13. | ⬜ |
| FR-AGENT-3 | S | The framework SHALL correlate agent events with editor events: an agent code block followed by a matching-size paste/injection within a window strengthens `origin: ai` (FR-INST-10); error-paste → agent turn → code-paste sequences SHALL be detectable as **reliance loops**. | RQ-P5: the human-agent interaction *dynamic*, not two silos. | ⬜ |
| FR-AGENT-4 | C | Additional source adapters (Copilot Chat export import; generic markdown/JSON conversation import) MAY be added behind the same event contract. | Extension point; proves FR-AGENT-1 is adapter-agnostic. | ⬜ |
| FR-AGENT-5 | M | Conversation **content policy** SHALL be protocol-declared and consent-matched: `metadata-only` (sizes/timings/counts only - the default), `redacted` (text with string literals and identifiers ≥ N chars masked), or `full`; the consent form generated for the study SHALL state the active policy verbatim. | Resolves the C1 tension for the one leg where content *is* the science; S2/S3. | ⬜ |

## FR-ING - Ingestion middleware

| ID       | P | Requirement | Rationale | Status |
| -------- | - | ----------- | --------- | ------ |
| FR-ING-1 | M | The middleware SHALL listen on port 8000 (configurable) and accept event batches over HTTP matching the extension's existing HttpSink payload, unchanged. | The built sink is the contract; the behavior doc's decoupled-sensor architecture. | ✅ MP-04 |
| FR-ING-2 | M | Ingestion SHALL be idempotent on `(sessionId, seq)`: replayed batches create no duplicates. | NFR-2; best-effort mirroring implies retries. | ✅ MP-04 |
| FR-ING-3 | M | The middleware SHALL detect and report per-session `seq` gaps. | NFR-2: loss must be *visible*, since prevention is best-effort. | ✅ MP-04 |
| FR-ING-4 | M | The middleware SHALL export a study's joined one-timeline dataset (all legs) as JSON and CSV. | Recipes and the dashboard consume one artifact. | ✅ MP-04 |
| FR-ING-5 | M | The middleware SHALL store uploaded files (session JSONL, consent artifacts, papers) indexed per study. | Gates and the knowledge layer need artifacts; S3. | ✅ MP-04 |
| FR-ING-6 | S | Ingested rows whose participant/condition are unknown to the protocol SHALL be stored and flagged, never dropped. | Data capture is subordinate to the study; defects become evidence (RQ-F2). | ✅ MP-04 |

## FR-DASH - Dashboard (the dynamic project manager)

| ID        | P | Requirement | Rationale | Status |
| --------- | - | ----------- | --------- | ------ |
| FR-DASH-1 | M | The dashboard SHALL show a study overview: protocol summary, RQs, planned-vs-collected sessions per condition. | S1 progress at a glance. | ✅ |
| FR-DASH-2 | M | The dashboard SHALL render the lifecycle as a board whose columns are phases and whose current state is computed from gate artifacts, not hand-set. | FR-PROT-3 made visible; S3. | ✅ |
| FR-DASH-3 | S | The dashboard SHALL show live sessions with recent events and seq-gap warnings. | C2 resolution: monitoring without interruption. | ✅ |
| FR-DASH-4 | M | The dashboard SHALL render a per-session swimlane timeline interleaving events from all legs on one time axis. | The one-timeline invariant made visible; the thesis screenshot. | ✅ |
| FR-DASH-5 | S | The dashboard SHALL show static-metric distributions split by condition. | RQ-P2 preview. | ✅ |
| FR-DASH-6 | S | Every chart SHALL display which RQ/requirement it answers, sourced from the protocol's analysis plan. | RQ-F2: visible traceability. | ✅ |
| FR-DASH-7 | M | The dashboard SHALL act as a **dynamic project manager**: a task board auto-derived from the protocol (every unsatisfied gate artifact, uncovered RQ, missing instrument config, un-run recipe, and integrity warning becomes a card with computed status), supporting researcher-added manual tasks alongside; cards clear themselves when the underlying condition is satisfied. | Supervisor's headline requirement: the study manages itself; nothing lives in a separate to-do app. | ✅ |
| FR-DASH-8 | S | The dashboard SHALL host the knowledge views: the related-papers graph (FR-LIT-2) and the assistant chat panel (FR-LIT-4). | One mission-control surface. | ✅ MP-10 |
| FR-DASH-9 | S | The dashboard SHALL explain itself in plain language: a first-run (and re-launchable) guided tour of every view, and hover tooltips for every requirement ID, research-question ID, and domain term it surfaces - tooltip text sourced from this SRS and the glossary at runtime so it cannot drift from the requirements of record. | S6/S7: researchers using the platform are not RE specialists; the owner himself could no longer decode the IDs. The platform must onboard a newbie unaided. | ✅ |

## FR-LIT - Knowledge layer (literature intelligence)

| ID       | P | Requirement | Rationale | Status |
| -------- | - | ----------- | --------- | ------ |
| FR-LIT-1 | M | The framework SHALL ingest papers by PDF upload and by arXiv ID / DOI, extracting metadata (title, authors, year, venue, abstract) and full text for the assistant. | Pre-study elicitation on-platform; S5 context. | ✅ MP-10 |
| FR-LIT-2 | M | The framework SHALL build a **related-papers graph** around ingested papers via a citation API (Semantic Scholar: references, citations, recommendations), rendered as an interactive graph in the dashboard - the ResearchRabbit-style view. | Elicitation support: find the studies you should be replicating/citing. | ✅ MP-10 |
| FR-LIT-3 | S | Papers SHALL be linkable to the protocol elements they justify (an RQ, an instrument, a metric, a recipe), and those links SHALL appear in the traceability views and the generated paper's related-work section. | Literature traceability: every metric has a citable origin (e.g. Miller's Law → parameter count). | ✅ MP-10 |
| FR-LIT-4 | M | The framework SHALL provide a **knowledge assistant**: natural-language Q&A over the study's papers, protocol, and dataset summaries, powered by the Claude API with tool use; every answer SHALL cite its sources (paper/section, protocol field, or query result). | "Ask Claude-like questions" - grounded, not vibes; S1/S4. | ✅ MP-10 |
| FR-LIT-5 | C | The framework MAY import a Zotero collection into the paper set. | One external integration proves the extension point. | ✅ |

## FR-ANA - Analysis & outputs

| ID       | P | Requirement | Rationale | Status |
| -------- | - | ----------- | --------- | ------ |
| FR-ANA-1 | M | Analyses SHALL be recipes: pluggable modules declaring `id`, `answers` (RQ ids), `requires` (data elements), emitting tables, figures, and methods text. | RQ-F3; papers become recipes. | ✅ |
| FR-ANA-2 | S | Recipe `requires` SHALL be validated against the protocol/dataset *before* data collection ends, failing loudly on missing data elements. | RQ-F2: catch design defects early. | ✅ |
| FR-ANA-3 | M | Recipes covering all pilot RQs SHALL be built in: fatigue-by-condition, stuck-episodes, tlx-debrief, paste-behavior, code-quality-by-condition, **ai-review-behavior** (review latency, scroll coverage, accept rate by suggestion size), **agent-interaction-dynamics** (turn cadence, prompt/response sizes, reliance loops, tool-call mix), **task-outcome-by-condition** (pass rates, time-to-first-green). | RQ-P1–P5. | ✅ |
| FR-ANA-4 | M | A runner SHALL execute the protocol's analysis plan and emit a per-study report organized by RQ. | Traceable results by construction. | ✅ |
| FR-ANA-5 | C | At least one published paper's analysis SHALL be implemented as a recipe, cited. | RQ-F3 proof of concept. | ✅ |
| FR-ANA-6 | M | The framework SHALL generate a **paper draft** from a completed study: Markdown + LaTeX skeleton with methods synthesized from the frozen protocol, results/figures/tables inserted from the recipe report per RQ, related work seeded from FR-LIT-3 links, and every generated claim carrying its traceability tag. | "Immediately extract a paper" - the write-up phase is a build artifact. | ✅ MP-11 (`analysis paper`; golden-file + tectonic-compile tests) |

## FR-META - Self-improvement (the framework studies itself)

| ID        | P | Requirement | Rationale | Status |
| --------- | - | ----------- | --------- | ------ |
| FR-META-1 | S | The framework SHALL log its own operational defects as structured findings - protocol validation failures, seq gaps, unknown-participant flags, gate blocks, recipe requires-failures, setup-friction notes - each linked to the requirement ID whose violation it evidences. | RQ-F2: the framework's flaws are data. | ✅ MP-11 (findings table + auto-scan for seq gaps + gate blocks; recipe requires-fails + `POST /findings`; dashboard finding cards) |
| FR-META-2 | S | After each study, a **retrospective** SHALL analyze the operational log and the facilitator's findings and produce a proposed changelist to the SRS / protocol schema / instrument configs (Claude-assisted drafting, human-approved before any change lands). | "Self-evolving and improving" - with a human gate, so change management stays RE-disciplined. | ✅ MP-11 (`analysis retrospective`; Claude-drafted proposal, FR-ETH-4 prompt boundary grep-tested, offline template fallback, inert until human-applied) |

## FR-ETH - Ethics & consent

| ID       | P | Requirement | Rationale | Status |
| -------- | - | ----------- | --------- | ------ |
| FR-ETH-1 | M | Ethics approval and per-participant consent SHALL be gate artifacts: `data-collection` is unreachable without them. | S3; C1. | ✅ MP-02+04 |
| FR-ETH-2 | M | Instruments SHALL NOT capture raw code content, raw keystrokes, or clipboard text; only aggregates, shapes, salted hashes, and workspace-relative paths. AI-lifecycle events record suggestion *sizes and timings*, never suggestion text. *(Rev 2, 2026-07-11: the agent leg and workspace snapshots are the scoped exceptions - governed by FR-AGENT-5's consent-matched content policy and the consent form's snapshot clause respectively; everything else stays content-free.)* | S2/S3; C1 resolution; binds FR-INST-5/8/9/10. | ✅ built instruments comply (MP-05: sizes/shapes/timings, salted in-memory hashes only); agent-leg exception lands with MP-12 |
| FR-ETH-3 | M | Participants SHALL appear in all stored data and outputs only as anonymized IDs; the ID↔identity mapping lives outside the framework. | S2/S3. | ✅ by construction |
| FR-ETH-4 | M | Knowledge-assistant calls to the Claude API SHALL send only paper text, protocol content, and aggregate dataset summaries - never row-level participant events. | NFR-5 boundary for the one cloud-touching feature. | ✅ MP-10 |

---

## Non-functional requirements

| ID     | P | Requirement | Rationale |
| ------ | - | ----------- | --------- |
| NFR-1  | M | **Non-intrusiveness.** No instrument may interrupt, block, or steal focus from the participant; sensors add no perceptible typing latency (fire-and-forget events to the local middleware, ActivityWatch-style); failures are swallowed, counted, reported once. | S2; C2; behavior doc's "no typing lag". |
| NFR-2  | M | **Data integrity.** Local JSONL is the source of truth; network mirroring is best-effort; loss must be detectable (seq gaps) even where not preventable. | S1's "never silently lose a session". |
| NFR-3  | M | **Portability.** Scientifically meaningful logic (heuristics, schedules, schemas, survey wording) stays IDE-agnostic (`src/core` never imports `vscode`). | Cross-IDE comparability; S6; FR-INST-7 later. |
| NFR-4  | M | **Extensibility.** All data schemas versioned; instruments and recipes plug in behind stable contracts without modifying existing legs. | S6; C4 resolution. |
| NFR-5  | M | **Privacy.** Data minimization per FR-ETH-2/3/4; all study data at rest stays on facilitator-controlled machines; nothing leaves without an export action; the sole external calls are the citation API (paper metadata only) and the Claude API (FR-ETH-4 bounds). | S2/S3; GDPR posture. |
| NFR-6  | S | **Reproducibility.** Pinned dependency versions; recipes deterministic given a dataset; report and paper-draft regeneration bit-stable modulo timestamps. | RQ-F3; S5. |
| NFR-7  | M | **Operational simplicity.** The full stack runs on one laptop, offline except FR-LIT/FR-META features, as `docker compose up` (middleware + dashboard; SonarQube optional profile). | S1: study day has no IT department. *(Promoted S→M for the production sprint.)* |
| NFR-8  | M | **Analytical honesty.** All statistical output reports exact tests, effect sizes, and per-cell n; no bare p-values; small-n framed as hypothesis-generating. | S4; pilot credibility. |
| NFR-9  | M | **Production readiness.** One-command bring-up with health checks, a seeded demo mode (replayed sample study) so every view renders without live participants, structured logs, and a smoke-test script that exercises ingest → dataset → report. "Inches from deployment" is testable, not a mood. | The one-week deliverable standard. |
| NFR-10 | S | **Build-vs-adopt discipline.** Every subsystem records an adopt / adapt / build / reject decision with rationale in `requirements/build-vs-adopt.md` before implementation. | S4 (engineering judgment is assessed); avoids NIH waste and dependency debt alike. |
