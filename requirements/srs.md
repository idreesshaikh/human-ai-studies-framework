# Software Requirements Specification

Requirements for the **Framework for Conducting Human-AI Studies**.
Direction of record: `docs/VISION.md` (v2 platform, 2026-07-17); the v1
sprint vision is preserved at `docs/archive/roadmap/00-VISION.md`. IDs
are stable (golden rule 2). **MoSCoW is defined per milestone**: v1
families carry priorities against the completed one-week sprint; v2
additions (FR-PLAT/TPL/CONV/CUR/AGF, FR-LIT-8/9/10, FR-PROT-9,
FR-INST-19, NFR-12 - marked *(v2)* in their rows) against the
thesis-final v2 milestone. Won't = deliberately deferred and argued as
such. Each v2 family row indexes a detailed spec in `specs/` (fit
criteria, data models, degradation posture); the SRS row wins on
conflict. Terms per `glossary.md`; status of record and elicitation log
in `traceability.md`; reuse decisions in `build-vs-adopt.md`.

Status key: ✅ built · 🔶 partial · ⬜ open · - deliberately not built.

**v2 platform re-alignment (2026-07-17, MP-01 rev 8 + rev 9).** Owner
direction: the framework becomes a multi-researcher platform whose core
interaction is the design conversation, grounded in the paper corpus,
with template-prescribed statistics and curated datasets beside live
capture. Full statement: `docs/VISION.md`; elicitation record:
`traceability.md` §3. The completed sprint's cut line and statuses are
untouched (golden rule 6).

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
| FR-PROT-9 | S | *(v2, added 2026-07-17; S against the v2 milestone.)* The protocol schema SHALL support **agent participants**: studies whose sessions are harness-executed runs of an agent under test (participant = anonymized agent-configuration ID recording tool + model), where `cognitiveOverlay` is optional and the agent leg + task harness are the primary instruments; validators SHALL accept such protocols under a bumped `protocolVersion` (consumers branch, never guess - FR-PROT-2). | The platform's agents-as-subjects claim (FR-AGF, FR-META-3) needs a runnable study type; half the measurement literature (SWE-Effi arXiv:2509.09853, AGENTS.md evaluations arXiv:2602.11988) is agent-only. Fit criterion: the draft fixture `protocol/examples/context-ablation-2026.yaml` validates unmodified except the version bump. | ⬜ draft fixture written |

## FR-INST - Instrumentation (the three legs)

| ID        | P | Requirement | Rationale | Status |
| --------- | - | ----------- | --------- | ------ |
| FR-INST-1 | M | The cognitive leg SHALL sample fatigue via Likert micro-probes timed into typing pauses, with jitter and a quiet tail. | RQ-P1; NFR-1. | ✅ Cognitive Overlay v0.1 |
| FR-INST-2 | M | The cognitive leg SHALL detect stuck episodes (dwell / scroll-thrash) and prompt inline without stealing focus. | RQ-P1; NFR-1. | ✅ |
| FR-INST-3 | M | Sessions SHALL be governed by a pausable, crash-recoverable clock ending in a TLX-style debrief. | RQ-P1; session integrity. | ✅ |
| FR-INST-4 | M | The static-metrics leg SHALL extract the full 9-metric cognitive-load matrix of `metrics/docs/static_code_metrics.md`: nesting depth penalty (exponential, tree-sitter), cognitive complexity (SonarQube API, stub-degradable), parameter count (Miller's Law rationale), Halstead mental effort (Radon), variable scope distance, indentation variance, line-width bounds, average identifier length, comment-to-code ratio - per-function and per-file as applicable. | RQ-P2; each metric maps to a working-memory / visual-friction construct. | ✅ MP-03 (9/9) |
| FR-INST-5 | M | The behavioral leg SHALL capture: tab/file focus switches (with workspace-relative paths), aggregated edit bursts (chars added/deleted, lines, duration, language), clipboard-paste events (size, line count, internal-copy latency - never content), file saves, and window/terminal focus. | RQ-P3; `extension/docs/developer_behavior_capture.md`; C1 resolution. | ✅ MP-05 |
| FR-INST-6 | M | Every data row of every leg SHALL carry the join keys (`participantId`, `condition`, `sessionId`, timestamp) and a schema version. | The one-timeline invariant; RQ-F1. | ✅ all four legs (overlay + behavioral MP-05, metrics MP-03, agent MP-12) |
| FR-INST-7 | W | A JetBrains adapter reusing the IDE-agnostic core. | NFR-3 makes it possible; thesis argues it, doesn't build it. | - |
| FR-INST-8 | M | The behavioral leg SHALL capture the AI-completion lifecycle: suggestion shown → accepted/rejected/dismissed, with **review latency** (time the suggestion was visible before the decision) and accepted-suggestion size. | RQ-P4 (how developers review AI code before accepting) - the Tako-informed differentiator. | ✅ MP-05 (blind spots in `extension/docs/adaptation-notes.md`) |
| FR-INST-9 | M | The behavioral leg SHALL track visible ranges (debounced top/bottom line per visible editor) so analysis can compute **scroll coverage** - whether AI-injected or multi-file changes were actually scrolled through before acceptance/save. | RQ-P4; `extension/docs/developer_behavior_capture.md` §Visual Viewing Ranges. | ✅ MP-05 |
| FR-INST-10 | M | Every edit burst SHALL carry an **origin classification**: `human` (incremental typing), `ai` (completion-event correlated, or block insertion above size/speed thresholds), `paste`, or `undo-redo`. Thresholds SHALL be protocol-configurable and the classification heuristic documented. | RQ-P3/P4: "if a massive block appears in 1 ms it was injected" - made rigorous. | ✅ MP-05 |
| FR-INST-11 | S | The behavioral leg SHALL classify active vs. idle time via WakaTime-style heartbeats (interaction within a rolling window), so time-on-task excludes editor-open-but-absent periods. | Honest denominators for all rate metrics. | ✅ MP-05 |
| FR-INST-12 | S | Behavioral capture SHALL be filterable to protocol-declared languages/paths (pilot: Python files in the task workspace only). | Data minimization (S2/S3); WakaTime language-filter pattern. | ✅ MP-05 |
| FR-INST-13 | S | All in-session prompts (fatigue probes, stuck prompts) SHALL render as translucent, glass-style in-editor surfaces layered over the code - never separate windows, screens, or apps; the participant's eyes stay on their work. | S2/NFR-1: cognitive-load sampling that doesn't itself add load. Debrief webview is already glassmorphic; probes upgrade from QuickPick where the API allows. | ✅ MP-05: in-editor everywhere; debrief glass; fatigue probe stays native QuickPick (no stable overlay-webview API - constraint in `extension/docs/adaptation-notes.md`) |
| FR-INST-14 | S | Session start SHALL record an environment snapshot event: VS Code version, extension versions, OS, agent tool + model identifier (AI condition), task ID. | S5: replication dies without environment provenance. | ✅ MP-05 |
| FR-INST-15 | S | The framework SHALL snapshot the task workspace over time (shadow git repo: commit on save + every N minutes, protocol-configurable) so static metrics can be computed as a **time series** and code evolution reconstructed, not just the final state. | RQ-P2 as trajectory; joins metrics leg to the timeline properly. | ✅ MP-12 (shadow-git snapshotter) |
| FR-INST-16 | M | Each task SHALL ship acceptance tests; the framework SHALL run them at session end (and optionally on save) and record pass/fail counts and time-to-first-green as events. | Outcome ground truth: without correctness, RQ-P2 measures style, not success. | ✅ MP-12 (task harness) |
| FR-INST-17 | S | The framework SHALL derive **code-evolution / process metrics** from the workspace-snapshot series (FR-INST-15) joined with origin-classified edit bursts (FR-INST-10): gross/net LOC added and deleted over the session, within-session **churn** (lines added then reworked or removed before session end), and **AI-code persistence** (fraction of AI-origin insertions surviving to session end); and SHALL record the participant's own VCS activity in the task repo as content-free `git_commit` events (hash, files changed, insertions, deletions, timing - never message text). *(Added 2026-07-12: elicitation from the metric-coverage review, `requirements/metric-coverage.md`.)* | Commits, LOC deltas, and churn are the most-reported telemetry metrics in LLM-assistant studies (SLR arXiv:2507.03156); persistence is Ziegler et al.'s (arXiv:2205.06537) second headline measure. Without them the code leg misses the literature's basic units, and the framework can't host those papers as recipes. | ✅ MP-12 (churn/persistence char-approximated, stated; line-level pending schema-v4 burst ranges) |
| FR-INST-18 | C | The behavioral leg SHOULD capture a content-free **IDE health stream**: workspace diagnostics counts by severity (errors/warnings, debounced on change) and build/test invocations outside the harness, as timeline events. *(Added 2026-07-12, same elicitation.)* | An error-count trajectory is an objective struggle proxy that joins fatigue probes and stuck episodes on the shared timeline; lab studies use it as a difficulty signal. Cheap via the VS Code diagnostics API; schema-v4 candidate. | ⬜ |
| FR-INST-19 | S | *(v2, added 2026-07-17.)* The cognitive leg SHALL support **comprehension probes**: short, timeboxed, protocol-configured checks (predict-output / locate-change) triggered when an agent-produced chunk is accepted and at maintenance-session defects, each response carrying the join keys plus a **chunk reference** joining it to the edit burst / agent turn that produced the chunk (never code content beyond FR-ETH-2 bounds). | The engagement → comprehension → maintenance chain (draft `protocol/examples/comprehension-debt-2026.yaml`, RQ-C1..C4) is unmeasurable without probe-to-chunk joins; nobody in the corpus instruments both ends (engagement self-reported in arXiv:2603.14225; ownership surveyed, not measured, in Martin-Lopez 2026). | ⬜ draft protocol written |

## FR-AGENT - Agent interaction leg (the fourth instrument leg)

| ID         | P | Requirement | Rationale | Status |
| ---------- | - | ----------- | --------- | ------ |
| FR-AGENT-1 | M | The framework SHALL capture agent interaction as structured events on the shared timeline (join keys + schema version like every leg): conversation turns (role, timing, text per content policy, code-block count/size/language), tool calls (name, duration, success), and session metadata (agent tool, model ID, token counts). | The agent is a study subject too: RQ-P5; feeds the dashboard like every other leg. | ✅ MP-12 |
| FR-AGENT-2 | M | The primary source adapter SHALL be Claude Code in the integrated terminal: real-time capture via Claude Code hooks POSTing to the middleware, plus post-session import of the on-disk transcript JSONL as the completeness backstop (hooks may miss what transcripts keep). The pilot's `ai-assisted` condition standardizes on this setup. | Only agent tool with lossless, machine-readable capture; decision D13. | ✅ MP-12 (hooks + transcript importer, one normalizer) |
| FR-AGENT-3 | S | The framework SHALL correlate agent events with editor events: an agent code block followed by a matching-size paste/injection within a window strengthens `origin: ai` (FR-INST-10); error-paste → agent turn → code-paste sequences SHALL be detectable as **reliance loops**. | RQ-P5: the human-agent interaction *dynamic*, not two silos. | ✅ MP-12 (correlate job: reliance loops + burst annotation) |
| FR-AGENT-4 | C | Additional source adapters (Copilot Chat export import; generic markdown/JSON conversation import) MAY be added behind the same event contract. | Extension point; proves FR-AGENT-1 is adapter-agnostic. | ⬜ |
| FR-AGENT-5 | M | Conversation **content policy** SHALL be protocol-declared and consent-matched: `metadata-only` (sizes/timings/counts only - the default), `redacted` (text with string literals and identifiers ≥ N chars masked), or `full`; the consent form generated for the study SHALL state the active policy verbatim. | Resolves the C1 tension for the one leg where content *is* the science; S2/S3. | ✅ MP-12 (`redact.py` choke point; `metadata-only` default, grep-the-output tested) |

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

*(v2 note, 2026-07-17: these rows are the built v1 operational console -
Svelte, D15 - which stays maintained-frozen until the v2 platform surface
(D34: React + shadcn/ui, `platform/` app, NFR-12) reaches parity
view-by-view; each migrated view retires its Svelte twin in the same PR.
The v2 surface's requirements live in FR-PLAT / FR-CONV / NFR-12.)*

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
| FR-LIT-5 | C | ~~The framework MAY import a Zotero collection into the paper set.~~ *(Withdrawn 2026-07-16, owner decision: importer removed - DOI/arXiv/PDF ingest covers the need; the extension point it proved is documented in D9.)* | One external integration proves the extension point. | ❌ withdrawn (was ✅ MP-09) |
| FR-LIT-6 | S | The knowledge view SHALL present the ingested papers as a visible, managed **library**: a list with add/remove, selection linked to the graph, and explicit progress feedback ("smart buffering") for any operation that waits on an external service - the UI never appears frozen or silently blocked. | Owner elicitation 2026-07-16: papers were only visible as graph nodes; slow citation-API calls looked like a hang. | ✅ built + gated (2026-07-16) |
| FR-LIT-7 | C | The citation-graph provider SHALL be replaceable behind the existing fetch seam (Semantic Scholar today, self-paced to its 1 req/s budget; OpenAlex is the recorded candidate if S2's experience stays poor). A swap is a build-vs-adopt decision, not a rewrite. | Owner elicitation 2026-07-16: "best experience" outranks any one provider. | ⏳ seam exists (`cached_fetch`/`get_json`); swap not yet decided |
| FR-LIT-8 | M* | *(v2, added 2026-07-17 rev 10; M against the v2 milestone.)* The platform corpus SHALL scale to **1,000 papers in two provenance tiers**: Tier A (hand-curated seeds with per-paper "why", `docs/papers/README.md`) and Tier B (pipeline-harvested via citation snowballing from Tier A - quality-gated, recency-weighted, connectivity-ranked, every row API-verified and carrying its discovery trail). The harvest pipeline SHALL be re-runnable (the corpus refreshes as literature moves) and SHALL be extensible to further discovery sources behind one adapter contract (agentic paper platforms - alphaXiv etc. - recorded as candidates in D36). **No corpus entry is ever synthesized**: unverifiable candidates are dropped, resolution failures reported. | Owner elicitation 2026-07-17: "grow to 1000, fresh precedence, cited too, quality only." The corpus feeds FR-CONV-2 grounding, FR-TPL grounding, and FR-LIT-9 matching. | 🔶 pipeline built (`scripts/corpus_harvest.py`); first full run + importer pending |
| FR-LIT-9 | M* | *(v2, rev 10.)* The platform SHALL **match papers to the researcher's idea as the design conversation unfolds**: candidate papers from the corpus (both tiers) surface as recommendation cards with a stated match reason and grounding chips; accepted papers join the study's paper set (one click, FR-LIT-1 flow) and immediately strengthen the conversation's grounding pool. Matching SHALL degrade gracefully: FTS relevance when no embedding/LLM ranking is available. | The "we give them the papers which closely match their idea" core; recommendation with stated reasons per the FR-CONV-2 no-unsourced-claims discipline. | ⬜ MP-15 |
| FR-LIT-10 | S | *(v2, rev 10.)* The study's knowledge SHALL be explorable as a **living literature view**: the citation graph animated as a responsive constellation that reacts to the conversation (papers glow when cited in a turn, drift into thematic clusters, newly added papers visibly arrive), doubling as the RAG surface - selecting papers scopes the assistant's retrieval to them ("talk to your papers"), with methodology/statistics guidance answered over that scope and every answer cited (FR-LIT-4 rules). Animation per NFR-12 (reduced-motion: the view stays fully functional statically). | Owner elicitation 2026-07-17: "animated visuals that talk to their papers... formations, statistics, methodology" - literature review as a living surface, not a list. | ⬜ MP-15/17 |

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
| FR-META-2 | S | After each study, a **retrospective** SHALL analyze the operational log and the facilitator's findings and produce a proposed changelist to the SRS / protocol schema / instrument configs (Claude-assisted drafting, human-approved before any change lands). | "Self-evolving and improving" - with a human gate, so change management stays RE-disciplined. | ✅ MP-11 (`analysis retrospective`; model-drafted proposal per D32, FR-ETH-4 prompt boundary grep-tested, offline template fallback, inert until human-applied) |
| FR-META-3 | S | The platform SHALL run **in-platform agents**: scheduled, autonomous workflows hosted by the middleware that (a) scan for operational findings and integrity gaps on a cadence, (b) draft retrospective/paper-suggestion digests grounded in the FTS5 knowledge index (the existing inverted-index RAG), and (c) surface their output as dashboard cards and inert proposals - never as unattended changes. Every agent obeys the FR-ETH-4 aggregates-only boundary and degrades gracefully offline. | Owner elicitation 2026-07-16: "things are inherently part of the platform to use" - automation must be built-in, not hand-run. | ⏳ specced as MP-13 (`docs/archive/roadmap/13-in-platform-agents.md`, 2026-07-16); build not started |

## FR-OPS - Deployment, releases & distribution (the adoption path)

Hosted instances exist so the platform can be *seen live and adopted* by
researchers in industry or academia (S6/S7) - they are demo/dev surfaces.
NFR-5 is untouched: real study data at rest stays on facilitator-controlled
machines; a public instance only ever carries the seeded demo study. The
cost constraint is a requirement, not a hope: everything below runs at $0
on GitHub Student Pack benefits (decisions D24-D28).

| ID       | P | Requirement | Rationale | Status |
| -------- | - | ----------- | --------- | ------ |
| FR-OPS-1 | S | The platform SHALL be deployable from its single container image (`middleware/Dockerfile` - one process serves API + dashboard, NFR-7) to (a) a free-tier container host as a public **seeded demo**, where an ephemeral disk is acceptable by design because the demo study reseeds itself on every boot (replay is idempotent, FR-ING-2), and (b) a persistent facilitator-controlled VM for dev/staging. All internet-facing instances SHALL serve TLS; any instance carrying more than the seeded demo SHALL additionally enforce the bearer token (`MIDDLEWARE_TOKEN`). | S6/S7 adoption: "see it live" without cloning; NFR-5 keeps real data off all of it; student credits keep it at $0. | 🔶 manifests + pipeline built; account provisioning pending |
| FR-OPS-2 | S | Releases SHALL be cut by pushing a git tag `vX.Y.Z` (release candidates: `vX.Y.Z-rc.N`): one pipeline re-runs the quality gates, builds the container image (pushed to GHCR tagged with the version), packages the extension `.vsix`, and publishes a GitHub Release with artifacts attached. RC tags SHALL be marked pre-release and deploy only to the demo instance; final tags SHALL pass a manual approval gate (GitHub environment) before the persistent instance updates. | Change management: what runs is a tagged, gated build - never a laptop artifact; RQ-F3 replication kits cite exact versions. | 🔶 pipeline built; first tagged release pending |
| FR-OPS-3 | S | The extension SHALL be distributed on the VS Code Marketplace, published by the release pipeline on final tags, so a facilitator installs it by ID and configures it entirely via `protocol derive overlay-settings` (FR-PROT-4) - no clone, no build step. RC builds SHALL be distributed as `.vsix` assets on GitHub pre-releases (the Marketplace rejects semver pre-release suffixes - D27). | "Anyone in industry or academia can conduct studies": install + derived settings = a working instrument leg. | 🔶 pipeline built; Marketplace publisher account pending |
| FR-OPS-4 | C | SonarQube SHALL remain **on-demand in every deployment**: locally the compose `--profile sonar`; in the cloud a deallocated VM that is started for analysis windows and deallocated after (workflow-dispatch or CLI), never a 24/7 service. The metrics orchestrator already stub-degrades to NaN with one warning when it is absent (D5). | The cognitive-complexity metric is batch-time, not session-critical; 4 GB of idle Java burns credit for nothing. | 🔶 workflow built; VM provisioning pending |
| FR-OPS-5 | S | Dashboard sign-in SHALL be a **pluggable auth provider** behind one seam: `none` (local, default when no token is set), `token` (the existing bearer token, zero-config self-hosting - stays the default whenever `MIDDLEWARE_TOKEN` is set), and `clerk` (hosted instances verify Clerk-issued JWTs against the instance's JWKS - D29). The dashboard SHALL present a sign-in surface instead of raw 401s. Ingest stays unauthenticated in every mode (NFR-1: sensors are fire-and-forget). External-service posture per NFR-4: every provider optional, replaceable, degrading gracefully. | Open-source self-hosters must never need a third-party account; the maintainer's hosted instance gets a polished login. | 🔶 seam + token sign-in built (2026-07-16); Clerk client widget pending account provisioning |
| FR-OPS-6 | C | The dashboard SHALL be hostable on a separate origin from the middleware for design iteration (D30 rev 2): the SPA takes an optional `VITE_API_BASE`, and the middleware SHALL allow cross-origin calls only from an explicit `MIDDLEWARE_CORS_ORIGINS` allow-list (unset = same-origin only, the default posture). | The owner iterates the dashboard visually in v0 (which now supports Svelte) against the hosted demo, without a framework change (D15) and without opening the API to arbitrary origins. | ✅ built + tested (2026-07-16) |
| FR-OPS-7 | S | Hosted deployments SHALL be **profile-oriented**: a signed-in Clerk identity (FR-OPS-5) becomes a user profile with per-user persisted preferences (theme, default assistant model, saved views) stored server-side, so the platform remembers each researcher across devices. Self-hosted `none`/`token` modes keep working profile-free. | Owner elicitation 2026-07-16: "persistent information and profile-oriented platform" - the reason Clerk was adopted (D29). | ⏳ requires Clerk provisioning (FR-OPS-5's pending half) first |

## FR-PLAT - Platform shell (multi-researcher workspace) *(v2, added 2026-07-17)*

Extends the identity work already built (FR-OPS-5 pluggable auth, FR-OPS-7
profiles). Serves S7 first. Detailed spec: `specs/fr-plat.md`; surface per
D34 + NFR-12.

| ID        | P | Requirement | Rationale | Status |
| --------- | - | ----------- | --------- | ------ |
| FR-PLAT-1 | M | The platform SHALL model **projects**: a collaborative workspace owning studies, papers, datasets, and members; every study SHALL belong to exactly one project. | S7: real research is collaborative and multi-study; the container the whole v2 flow hangs off. | ⬜ |
| FR-PLAT-2 | M | A signed-in identity (FR-OPS-5) SHALL resolve to project memberships with a **role** (`owner` \| `researcher` \| `viewer`); the owner manages membership; permissions SHALL be enforced server-side, never UI-only. | S7 invites colleagues with bounded access; S3: role boundaries are a data-protection control. | ⬜ |
| FR-PLAT-3 | S | Members SHALL be invitable by email link, landing with the assigned role after sign-in. | S7 onboarding without an admin. | ⬜ |
| FR-PLAT-4 | S | The platform SHALL present a public **hero page**: what it does, entry to the live seeded demo, and sign-up - readable by a lay researcher per NFR-11. | S7's first minute decides adoption. | ⬜ |
| FR-PLAT-5 | S | Self-hosted `none`/`token` deployments (FR-OPS-5) SHALL keep working project-free: a single implicit project, no sign-up, no regression for the one-facilitator laptop posture. | S1/NFR-7: the platform grows outward without breaking the study-day core. | ⬜ |

## FR-TPL - Study templates (paper-derived designs) *(v2, added 2026-07-17)*

Published designs become parameterized protocol generators, grounded in
the corpus (`docs/papers/README.md`); generalizes RQ-F3 from "replicate
our study" to "replicate the literature's designs". Detailed spec:
`specs/fr-tpl.md`.

| ID       | P | Requirement | Rationale | Status |
| -------- | - | ----------- | --------- | ------ |
| FR-TPL-1 | M | The platform SHALL provide a **study-template registry**: parameterized, citable encodings of published study designs (design type, conditions, instruments, measures, session plan, analysis plan) that instantiate into a valid protocol (FR-PROT-1). | RQ-F3 generalized; S7: pick a design, don't reinvent it. Seed candidates: METR RCT (arXiv:2507.09089), Ziegler telemetry+survey (arXiv:2205.06537), HAI-Eval within-subject (arXiv:2512.04111), Cursor-style repo mining (arXiv:2511.04427). | ⬜ |
| FR-TPL-2 | M | Every template SHALL bind a **statistical plan**: the exact tests, effect sizes, corrections, and per-cell-n rules its design requires (NFR-8 by construction), emitted into the instantiated protocol's analysis plan so the researcher gets correct statistics without deriving them. | Owner elicitation 2026-07-17: the statistical formulation is the step researchers most fear getting wrong. Anchored in Baltes et al. guidelines (arXiv:2508.15503). | ⬜ |
| FR-TPL-3 | S | *(Rev 2, 2026-07-17: the design conversation FR-CONV-1 is the primary designer.)* The structured **study designer** SHALL be the synchronized review surface over the same protocol draft - template parameters, the dataset-exists branch, slot-completeness - with edits in either surface reflected in the other; the form alone SHALL remain a complete no-LLM path. | S7 reaches a valid protocol conversationally or structurally; the form is also the FR-CONV degradation path (no key → still fully usable). | ⬜ |
| FR-TPL-4 | S | Templates SHALL cite their source papers by `paperRef` and surface in the knowledge layer (graph, assistant, FR-LIT-2/4), so "replicate this paper" is navigable from the literature view and every template answer is grounded. | Papers-become-recipes (FR-ANA-5) extended to papers-become-designs; literature traceability (FR-LIT-3). | ⬜ |
| FR-TPL-5 | C | Third-party templates MAY be contributed behind the same contract (schema validation + mandatory citation), reviewed before publication in the registry. | S6 extension point; community growth without methodology dilution. | ⬜ |

## FR-CONV - Conversational study design *(v2, added 2026-07-17 rev 9)*

**The platform's core interaction.** Detailed spec: `specs/fr-conv.md`.
Guardrails: the protocol (YAML) stays the sole document of record; the
lifecycle governs change; FR-ETH-4 binds the design assistant.

| ID        | P | Requirement | Rationale | Status |
| --------- | - | ----------- | --------- | ------ |
| FR-CONV-1 | M | Every study SHALL have a persistent **design conversation** - the primary surface through which a study is elicited, designed, and evolved; platform proposals arrive as individually acceptable/rejectable **design moves**, streamed, multi-user with per-turn attribution. | Owner elicitation 2026-07-17: "experiments are built from conversations." LLM-led elicitation is viable (arXiv:2507.02564); follow-up questions beat forms (arXiv:2603.04244). | ⬜ MP-15 |
| FR-CONV-2 | M | Every design move SHALL carry **grounding** (citations into the paper corpus, template registry, or SRS/glossary) or be visibly labeled unsourced; the assistant may only cite sources retrieved in that exchange; counter-evidence in the corpus SHALL be surfaced against conflicting researcher choices. | "Ideas are grounded in science" - the corpus is the product's knowledge; trust calibration demands labeled provenance (arXiv:2312.10893). | ⬜ MP-15 |
| FR-CONV-3 | M | Accepted design moves SHALL **compile deterministically** (no LLM in the compile step) into a protocol draft diff, validated on every compile, applied only on role-checked human approval; validation failures thread back into the conversation. | The conversation proposes; the protocol remains the requirements spec (RQ-F1); determinism per NFR-6. | ⬜ MP-15 |
| FR-CONV-4 | S | Mid-study design/instrumentation changes SHALL route through **phase-aware amendment rules**: post-ethics amendments produce version bumps + amendment records; consent-relevant changes block new data-collection sessions until re-approval; running sessions are never reconfigured (NFR-1). | "Evolved on the fly" without breaking S3's invariant: the approved protocol is the executed protocol, drift is version-visible. | ⬜ MP-18 |
| FR-CONV-5 | S | Researcher feedback SHALL be capturable in-conversation as structured findings feeding the retrospective and in-platform agents (FR-META-1/2/3) as inert, human-approved proposals; cross-project learning uses aggregates only, never conversation text. | "The platform evolves based on people's feedback" - the self-application thesis; stall-point taxonomy per arXiv:2601.22208. | ⬜ MP-18 |
| FR-CONV-6 | M | The full conversation (turns, moves, decisions, compilations, approvals) SHALL be stored as the study's **elicitation record** - the traceable chain conversation turn → design move → grounding → protocol hunk → data element → claim - exportable, and includable (opt-in) in replication kits. | The RE contribution: elicitation captured by construction; S4's traceability chain gains its origin end. | ⬜ MP-15 |

## FR-CUR - Curated datasets (the second data path) *(v2, added 2026-07-17)*

Studies over existing data (repository mining, archives) become first-class
alongside live instrumented sessions - one analysis pipeline for both.
Detailed spec: `specs/fr-cur.md` (normalizer contract, GitHub adapter,
validity-threats record schema).

| ID       | P | Requirement | Rationale | Status |
| -------- | - | ----------- | --------- | ------ |
| FR-CUR-1 | M | The platform SHALL support studies whose data is a **curated dataset**: rows imported from external sources, normalized into the one-timeline event schema with the join keys (FR-INST-6) and a schema version, so recipes (FR-ANA-1) consume curated and live datasets identically. | The mined-study family (Cursor arXiv:2511.04427, AIDev arXiv:2602.09185) is half the empirical literature; the join-key contract is what makes one platform serve both. | ⬜ |
| FR-CUR-2 | S | A GitHub **mining adapter** SHALL import repositories, pull requests, commits, and issues via the GitHub API into curated-dataset rows - rate-limited, cached, resumable, degrading gracefully (NFR-4 external-service posture). | The literature's dominant source (AIDev, Agentic Much? arXiv:2601.18341); adapter proves FR-CUR-1 is source-agnostic. | ⬜ |
| FR-CUR-3 | S | Every curated dataset SHALL carry a **validity-threats record** - sampling frame, inclusion criteria, known biases, heuristics used - surfaced in reports (FR-ANA-4) and paper drafts (FR-ANA-6). | Robbes et al.'s mining pitfalls (arXiv:2601.18345) made structural; NFR-8 honesty extends to data provenance, not just tests. | ⬜ |
| FR-CUR-4 | C | Published replication packages and research archives (e.g. DevGPT, arXiv:2309.03914) MAY be importable behind the same normalizer contract. | Closes the loop: replication kits we *emit* (FR-PROT-7) and archives we *consume* speak one schema. | ⬜ |

## FR-AGF - Agent-friendliness (machine-readable platform) *(v2, added 2026-07-17)*

AI agents are operators of the platform, not just study subjects.
Detailed spec: `specs/fr-agf.md` (manifest schema, generated context
files, annotation convention).

| ID       | P | Requirement | Rationale | Status |
| -------- | - | ----------- | --------- | ------ |
| FR-AGF-1 | S | Deployments SHALL expose a **platform manifest**: machine-readable capabilities, API surface, event schemas, glossary, and requirements - extending the existing `/requirements` + `/glossary` endpoints (FR-DASH-9) - so an agent can discover the platform's semantics without scraping. | Owner elicitation 2026-07-17: "agents friendly, with a lot of metadata that agents when run can understand"; FR-META-3's in-platform agents are the first consumer. | ⬜ |
| FR-AGF-2 | S | Repository and deployments SHALL ship agent context files (the AGENTS.md pattern) **generated from the documents of record** (SRS, glossary, protocol schema), never hand-maintained copies that drift. | Context files measurably steer agents (arXiv:2602.11988, arXiv:2601.20404); drift-free by the same rule as FR-DASH-9 tooltips. | ⬜ |
| FR-AGF-3 | C | Dashboard surfaces MAY carry stable semantic annotations (`data-*` attributes) so browser-driving agents can operate the UI reliably. | Extension point; zero cost when unused. | ⬜ |

## FR-ETH - Ethics & consent

| ID       | P | Requirement | Rationale | Status |
| -------- | - | ----------- | --------- | ------ |
| FR-ETH-1 | M | Ethics approval and per-participant consent SHALL be gate artifacts: `data-collection` is unreachable without them. | S3; C1. | ✅ MP-02+04 |
| FR-ETH-2 | M | Instruments SHALL NOT capture raw code content, raw keystrokes, or clipboard text; only aggregates, shapes, salted hashes, and workspace-relative paths. AI-lifecycle events record suggestion *sizes and timings*, never suggestion text. *(Rev 2, 2026-07-11: the agent leg and workspace snapshots are the scoped exceptions - governed by FR-AGENT-5's consent-matched content policy and the consent form's snapshot clause respectively; everything else stays content-free.)* | S2/S3; C1 resolution; binds FR-INST-5/8/9/10. | ✅ all legs comply (MP-05 sizes/shapes/timings, salted in-memory hashes; agent-leg scoped exception via FR-AGENT-5, MP-12) |
| FR-ETH-3 | M | Participants SHALL appear in all stored data and outputs only as anonymized IDs; the ID↔identity mapping lives outside the framework. | S2/S3. | ✅ by construction |
| FR-ETH-4 | M | Knowledge-assistant calls to the ~~Claude API~~ LLM provider *(rev 2, 2026-07-16: the D32 provider, Mistral as of D32 rev 2 - the boundary is provider-independent)* SHALL send only paper text, protocol content, and aggregate dataset summaries - never row-level participant events. | NFR-5 boundary for the one cloud-touching feature. | ✅ MP-10; provider swapped under D32, boundary tests unchanged |

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
| NFR-11 | S | **Two-layer documentation (plain language outside, IDs inside).** Requirement/decision IDs (`FR-*`, `NFR-*`, `MP-*`, `D*`) live in `requirements/` and `docs/archive/` only. Every public-facing surface - README, RUNBOOK, TOUR, contributor guide, dashboard UI copy - uses plain names ("the paper generator", "the study timeline"); the dashboard keeps its traceability chips but leads with the plain name and reveals the formal ID + SRS text on hover (FR-DASH-6/9 satisfied, inverted). Code comments keep citing IDs (they are in-code traceability). *(Added 2026-07-16: the platform is open source and must read as a product; the RE record remains complete underneath - two audiences, two layers.)* | S6/S7 + open-source adoption: lay readers get a product, the examiner gets an intact traceability spine. |
| NFR-12 | M* | **Experience quality** *(v2, added 2026-07-17; M against the v2 milestone)*. Every v2 surface meets a product bar, specified testably in `specs/nfr-12-experience.md`: one token system shared by UI and charts (D34 shadcn/ui vendored; the dataviz palette stays the chart source of truth); light+dark with no flash; motion that communicates state, honoring `prefers-reduced-motion`; skeletons/streaming so no surface ever appears frozen (FR-LIT-6 generalized); conversation output chunked into individually decidable cards, never prose walls (arXiv:2603.14225); WCAG 2.2 AA with axe-clean CI on core flows; keyboard-only completion of the design walkthrough. | Owner direction 2026-07-17 ("beautiful, modern, fluid"); S7 credibility - the platform must look like it knows what it's doing; D34/D35. |
