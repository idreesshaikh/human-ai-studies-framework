# Traceability matrix (living document)

The status of record. A requirement is done only when its row here is flipped
and its verification steps are green. Status: ✅ done · 🔶 partial · ⬜ open ·
⏳ blocked · - deliberately not built.

## 1. Requirement → source → implementation

| Requirement | Traces to (RQ / stakeholder / source) | Where it lives | Status |
| ----------- | ------------------------------------- | -------------- | ------ |
| FR-PROT-1 | RQ-F1; S1,S3,S5 | `protocol/` schema | ✅ |
| FR-PROT-2 | RQ-F1; S6 | `protocol/` schema | ✅ |
| FR-PROT-3 | RQ-F1,F2; S1,S3 | `protocol/lifecycle.py` | ✅ |
| FR-PROT-4 | RQ-F1; S1 | `protocol/cli.py` derive | ✅ |
| FR-PROT-5 | RQ-F2; S1,S4 | protocol analysis plan | ✅ |
| FR-PROT-7 | RQ-F3; S5 | replication-kit export | ✅ (`protocol export replication-kit`; byte-identical reproduction test) |
| FR-PROT-8 | (deferred vision) | - | - |
| FR-PROT-9 | RQ-A1–A3; FR-AGF | protocol schema (agent participants) + fixture `protocol/tests/fixtures/agent-participant-v3.yaml` + `derive` agent-branch | ✅ fixture validates; overlay-derive fails cleanly + `derive agent-hooks` produces harness config |
| FR-PROT-10 | RQ-F1; S1,S3; FR-DASH-2 | `protocol/lifecycle.py` `gates_by_phase` implicit completion attestation; attested via lifecycle board | ✅ gateless phases need explicit advance; tests in `protocol/tests/test_lifecycle.py` + `middleware/tests/test_middleware_api.py` |
| FR-INST-1 | RQ-P1; S1 | TERN `surveys/fatiguePrompt` | ✅ |
| FR-INST-2 | RQ-P1; S1 | TERN `stuckDetector/stuckPrompt` | ✅ |
| FR-INST-3 | RQ-P1; S1,S2 | TERN `session/endSurvey` | ✅ |
| FR-INST-4 | RQ-P2; S1 | `metrics/` | ✅ 9/9 (cognitive complexity stub-degradable per D5) |
| FR-INST-5 | RQ-P3; S1,S2 | TERN behavioral leg | ✅ |
| FR-INST-6 | RQ-F1; all legs | join keys in every leg | ✅ all four legs |
| FR-INST-7 | (deferred vision); S6 | - | - |
| FR-INST-8 | RQ-P4; D2 (Tako) | overlay AI-lifecycle events | ✅ (blind spots in `extension/docs/adaptation-notes.md`) |
| FR-INST-9 | RQ-P4 | overlay visible-range tracker | ✅ |
| FR-INST-10 | RQ-P3,P4 | overlay origin classifier (`src/core`) | ✅ |
| FR-INST-11 | RQ-P3; D4 (WakaTime) | overlay heartbeat/idle (`src/core`) | ✅ |
| FR-INST-12 | S2/S3; D4 | overlay capture filters | ✅ |
| FR-INST-13 | S2; NFR-1 | overlay prompt surfaces | ✅ in-editor everywhere; debrief glass; fatigue probe stays native QuickPick (no stable overlay-webview API) |
| FR-INST-14 | S5 | overlay environment_snapshot event | ✅ |
| FR-INST-15 | RQ-P2 time series; D14 | workspace snapshotter (shadow git) | ✅ |
| FR-INST-16 | outcome ground truth | task harness | ✅ |
| FR-INST-17 | RQ-P2/P3/P4; D14 | code-evolution derivation + `git_commit` events | ✅ derivation + content-free `git_commit`; churn/persistence char-approximated (line-level pending) |
| FR-INST-18 | RQ-P1/P3 struggle proxy | overlay diagnostics/health stream | ✅ IDE health stream implemented: `IdeHealthCollector` (debounced counter, content-free by construction in `src/core/ideHealth.ts`) + `VscodeIdeHealthAdapter` (VS Code diagnostics subscriber in `src/vscode/ideHealth.ts`); backend toggle catalog includes `ideHealth.enabled` entry with FR-INST-18 grounding |
| FR-INST-19 | RQ-C1–C4 | comprehension-probe instrument (overlay + probe bank + chunk reference) | ✅ Phase 21 |
| FR-AGENT-1 | RQ-P5; S1 | agent leg event contract | ✅ |
| FR-AGENT-2 | RQ-P5; D13 | Claude Code hooks + transcript importer | ✅ |
| FR-AGENT-3 | RQ-P5 | correlation job (reliance loops + burst annotation) | ✅ |
| FR-AGENT-4 | S6; extension point | Copilot/generic import adapters | ✅ Phase 24 — generic-json format in `transcript.py`, 10 new tests (normalization + content policy + format auto-detect) |
| FR-AGENT-5 | S2,S3; C1 | content-policy redactor + consent generator | ✅ |
| FR-ING-1 | S1; NFR-2; D3 | `middleware/` :8000 ingest | ✅ |
| FR-ING-2 | NFR-2; S1 | `middleware/` | ✅ |
| FR-ING-3 | NFR-2; S1 | `middleware/` gap report | ✅ |
| FR-ING-4 | RQ-P1–P4; S1,S5 | `middleware/` dataset export | ✅ |
| FR-ING-5 | S3; FR-ETH-1; FR-LIT-1 | `middleware/` file store | ✅ |
| FR-ING-6 | RQ-F2 | `middleware/` protocol check | ✅ |
| FR-DASH-1 | S1 | `platform/` study overview | ✅ |
| FR-DASH-2 | RQ-F1; S1,S3 | `platform/` lifecycle board | ✅ |
| FR-DASH-3 | S1; C2 | `platform/` session status | ✅ |
| FR-DASH-4 | RQ-F1; S1,S4 | swimlane timeline | ✅ Phase 23 |
| FR-DASH-5 | RQ-P2; S1 | `platform/` metric strip | ✅ |
| FR-DASH-6 | RQ-F2; S4 | `platform/` trace chips | ✅ |
| FR-DASH-7 | S1; RQ-F2 | self-computing status view (derived from the protocol) | ✅ |
| FR-DASH-8 | S1 | `platform/` knowledge views (constellation + assistant) | ✅ |
| FR-DASH-9 | S6,S7 | vocabulary tooltips; middleware `/requirements` + `/glossary` | ✅ tooltip/vocabulary layer (standalone guided tour dropped; hero + demo onboard) |
| FR-LIT-1 | S1,S5; D8 | middleware paper ingest + extraction | ✅ id + PDF path (D21); FTS5 index |
| FR-LIT-2 | S1; D7,D8 | citation constellation (S2 API + `platform/`) | ✅ edge harvest + stub nodes + force-graph |
| FR-LIT-3 | RQ-F2; S4 | paper↔protocol links | ✅ seeded from protocol `literature:`, editable |
| FR-LIT-4 | S1,S4; D32; FR-ETH-4 | knowledge assistant (LLM tool-use) | ✅ cited answers, graceful without key |
| FR-LIT-6 | S1 | library list (select/remove) + busy spinner with plain-language wait copy | ✅ |
| FR-LIT-7 | S1; D8 | provider seam (`semantic_scholar.get_json` + `cached_fetch`); OpenAlex recorded as swap candidate | ⏳ seam ready, swap undecided |
| FR-LIT-8 | FR-CONV-2, FR-TPL; D8, D36 | `scripts/corpus_harvest.py` + `docs/papers/corpus-index.json`/`CORPUS.md`; `corpus_importer.py` | 🔶 pipeline + verified run; importer lands Tier A + Tier B as `Paper(tier=…)` rows + FTS + seed edges; committed re-harvest pending |
| FR-LIT-9 | FR-CONV-2; RQ-F4 | paper matcher (FTS→LLM ladder) + recommendation cards | ✅ real ladder (FTS BM25 + seed-connectivity + optional LLM rerank); `/papers/match` + `/papers/from-match` |
| FR-LIT-10 | NFR-12; FR-LIT-4; FR-ETH-4 | living literature constellation + scoped RAG | ⬜ |
| FR-ANA-1 | RQ-F3; S5,S6 | `analysis/core.py` | ✅ |
| FR-ANA-2 | RQ-F2 | `analysis/` requires-check | ✅ |
| FR-ANA-3 | RQ-P1–P4 | built-in recipes | ✅ (agent/outcome recipes run once agent-leg data lands) |
| FR-ANA-4 | RQ-F2; S1,S4 | `analysis/` runner+report | ✅ |
| FR-ANA-5 | RQ-F3 | replicated-paper recipes | ✅ two cited replications: `ziegler-acceptance-rate` + `meyer-fragmentation` |
| FR-ANA-6 | S1,S4 | paper-draft generator | ✅ (`analysis paper`; golden-file + tectonic-compile tests) |
| FR-ANA-7 | S7 | `suggest_figures.py` deterministic figure suggestion | ✅ Phase 22 — 6 result shapes covered, ranked shortlists with rationale |
| FR-ANA-8 | NFR-4 | parameterised recipes (two-group-nonparametric, paired-nonparametric, two-proportion, correlation) | ✅ Phase 22 — each reads params from `dataset.meta` (value columns, figure form, test/effect-size); runner injects per-recipe params from analysisPlan |
| FR-META-1 | RQ-F2 | operational findings log (middleware) | ✅ auto-scan (seq-gap/gate-block) + recipe requires-fails + `POST /findings`; extended with a `feedback` kind (FR-CONV-5.1) |
| FR-META-2 | RQ-F2; D32 | retrospective (LLM-assisted, human-approved) | ✅ inert proposal; extended to draft from feedback findings + anonymous shapes (FR-CONV-5.2) |
| FR-META-3 | FR-META-1/2; FR-ETH-4 | in-platform scheduled agents over the FTS5 index | ⏳ specced (`docs/roadmap/18-evolution.md` extends the machinery); not built |
| FR-OPS-1 | S6,S7; NFR-5 | `railway.toml` + `middleware/Dockerfile` + `middleware/scripts/start_with_seed.sh` + `docker-compose.yml` + `.github/workflows/deploy.yml` | 🔶 manifests + pipeline built; hosting provisioning pending (RUNBOOK §9) |
| FR-OPS-2 | change management; RQ-F3; NFR-9 | `.github/workflows/release.yml` + `deploy.yml` (GHCR, D24) | 🔶 built; first tagged release pending |
| FR-OPS-3 | S6,S7; FR-PROT-4 | `release.yml` marketplace job (D27); `extension/package.json` | 🔶 built; publisher account + `VSCE_PAT` pending |
| FR-OPS-4 | D5; zero-idle-cost | `.github/workflows/sonar-vm.yml` + `docker-compose.yml` `--profile sonar` + `metrics/src/analyzers/sonar_metrics.py` (stub-degradable) | 🔶 workflow built; VM provisioning pending (RUNBOOK §9) |
| FR-OPS-5 | NFR-1 (ingest open); D29 | `middleware/auth.py` (none/token/clerk) + `GET /auth/config` + `platform/src/lib/auth.tsx` + `SignInScreen` (hotloaded `@clerk/clerk-js`/`@clerk/ui`, token-paste fallback) | ✅ code complete (2026-07-20, rebuilt in `platform/` after the `dashboard/` retirement dropped it); live Clerk smoke pending |
| FR-OPS-6 | D30; D34 | `platform/` `VITE_API_BASE` + `settings.cors_origins` → opt-in `CORSMiddleware` | ✅ |
| FR-OPS-7 | D29; FR-OPS-5 | per-user preference store keyed by Clerk identity | ⏳ blocked on Clerk provisioning |
| FR-OPS-8 | S6,S7; FR-INST-20 | `extension/` packaging + release CI | ⬜ Phase 25 — publisher id still `replace-with-your-vsce-publisher-id` |
| FR-PLAT-1 | S7 | project/membership/invitation model + boot migration (`db.py`); scoping choke point (`authz.require_project*`) | ✅ backend + tests; `platform/` projects UI — `createApi()` (`api.ts`) fixed 2026-07-20 to default same-origin (NFR-7) instead of always falling back to the in-memory fake whenever `VITE_API_BASE` was unset, which had silently made every deployment (including the seeded demo) run on fake, non-persistent project/member data regardless of the real backend |
| FR-PLAT-2 | S7,S3; FR-OPS-5 | roles + server-side enforcement (`authz.CAPABILITIES` matrix as data) | ✅ matrix-complete tests; `RoleGate` reflects it client-side (UI only) |
| FR-PLAT-3 | S7 | invitations (single-use, expiring); `InviteDialog` (copy-link) | ✅ backend + UI; email-provider delivery deferred |
| FR-PLAT-4 | S7; NFR-11 | hero page | ✅ the hero is a self-contained animated showcase: an ambient "living literature constellation" (`Constellation.tsx`) behind a deterministic, no-LLM core-loop demo (`HeroShowcase.tsx`) — question types itself, a grounded design-move card folds in, citation chips light. The earlier embedded live-LLM demo (`/demo/conversation/turns` + `<ConversationView demo>`) was removed on 2026-07-23 as unreliable; nothing here makes a network call, so it never breaks. Reduced-motion renders the settled final frame. |
| FR-PLAT-5 | S1; NFR-7 | implicit-project fallback (`none`/`token`) | ✅ implicit project + permissive-sink preserved |
| FR-PLAT-6 | S7 | live presence + study-change push (SSE, in-process hub) | ✅ `presence.py` hub + `/studies/{id}/presence/stream`; publishes on turn/move/draft; `test_presence.py` |
| FR-TPL-1 | S7; RQ-F3 | study-template registry (`template_registry.py` + `templates/`) | 🔶 versioned registry + two-layer validation + typed instantiation; 13 templates ship (2 original seeds + Phase 22's 8 Wave-1 archetypes + `hai-eval-synergy-v1` promoted 2026-07-21 + Wave-2's first fill `survey-self-report-v1`/`observational-field-v1`, 2026-07-21); `cursor-mining-v1` remains in `templates/drafts/`, blocked on repository-trend recipes (`validate_registry()`'s recipe-existence check passes on id alone, not measurement-unit fit) — see `templates/drafts/README.md` |
| FR-TPL-2 | S7; NFR-8 | template-bound statistical plans + deterministic prescription table (`prescribe.py`) | 🔶 each shipped template binds its `statisticalPlan`; prescription table covers all design shapes; bespoke prescription compiles into analysisPlan (Phase 22 Slice A/C) |
| FR-TPL-3 | S7; RQ-F1 | guided study designer (synchronized no-LLM form) | ⬜ conversation is the primary designer (FR-CONV-1 ✅); the form review surface is not yet built |
| FR-TPL-4 | RQ-F3; FR-LIT-3 | template↔paper links in knowledge layer | 🔶 template `source` cites corpus papers; graph nodes wired via `list_templates()` `source` field (Phase 22) |
| FR-TPL-5 | S6 | community template contract | ✅ Phase 24 Slice C — TemplateSubmission model + endpoints (submit, list, get, approve/reject), 11 tests |
| FR-TPL-6 | S7; NFR-8 | `prescribe.py` deterministic prescription table | ✅ Phase 22 — 8 design shapes covered, each with test/effect-size/correction/rationale |
| FR-TPL-7 | S7 | design-archetype template registry (8 Wave-1 archetypes) + `design_assistant.recommend_templates` | 🔶 Wave 1's 8 archetypes exist and validate; keyword-based template matching wired in `design_assistant.respond()`; ranked `/templates/match` endpoint not yet built — see Phase 22 |
| FR-CONV-1 | S7; RQ-F4 | design conversation (`platform/` + middleware threads) | ✅ server-driven conversation; researcher text → grounded reply → move cards → validating draft in-conversation; now LLM-primary/scripted-fallback per FR-CONV-8 — token streaming still pending |
| FR-CONV-2 | RQ-F4; FR-ETH-4 | grounding contract (cite-what-you-retrieved) | ✅ grounding built only from retrieved rows, asserted server-side; unsourced compiles with `grounding: none` |
| FR-CONV-3 | RQ-F1, RQ-F4; NFR-6 | deterministic move→YAML compiler + diff approval | ✅ pure `(base, moves) → draft`, byte-identical replay; validate every compile; apply only through a recorded, role-checked approval |
| FR-CONV-4 | S3; FR-PROT-2/3; NFR-1 | phase-aware amendment engine (`evolution.py`) | 🔶 consent-relevance rule + amendment routing + session-start gate + version chips + ethics-board summary; UI built + gated; live transport deferred |
| FR-CONV-5 | RQ-F2; FR-META-1/2/3 | in-conversation feedback → findings pipeline | 🔶 marked turn → `feedback` finding with locus; inert retrospective cites findings + anonymous shapes (grep-the-output enforced); UI built + gated |
| FR-CONV-6 | S4; RQ-F4; C3 | elicitation record store + chain export | ✅ append-only turns/moves/compilations/approvals + `/conversation/export`; the chain renders both directions; redaction leaves the graph intact |
| FR-CONV-9 | S7 | experience-adaptive conversation (student / new / experienced / industry) | ✅ `elicitation.PROFILES` + `researcherProfile` pref; `/conversation/profiles`; `test_elicitation.py` |
| FR-CONV-10 | S7; S4 | elicitation before proposal + answer-the-question fidelity | ✅ `elicitation.assess_understanding` / `classify_turn`, `design_assistant.turn_stance` + `_permitted_moves`, moves carried in LLM history; `test_elicitation.py` |
| FR-CONV-7 | FR-CONV-4.2 | `middleware/` evolution.py `consent_relevance` | ✅ implemented + parametrized test (nested `enabled` change and first-appearance-of-subtree cases in `test_consent_relevance_rule`) |
| FR-CONV-8 | FR-CONV-1/2; NFR-4/5 | `middleware/design_llm.py` + `assistant.py`'s provider seam (`MistralProvider`/`OpenAICompatibleProvider`) + `design_assistant.respond()` | ✅ retrieval-first candidate menu, JSON-schema-validated moves, refs filtered against the menu (wall #3 enforced twice with `_resolve_grounding`), scripted fallback on any failure; `test_design_llm.py` + `test_conversation.py`'s LLM/fallback/no-key cases |
| FR-CUR-1 | RQ-F3; FR-INST-6 | curated-dataset normalizer (`curated/`: contract, schema vocab, pseudonymize, frame) | ✅ normalizer + salted-hash actors + schema events; static metrics over mined code reuse the metrics leg |
| FR-CUR-2 | S7; NFR-4 | GitHub adapter + versioned heuristics + job runner (`middleware/mining.py`); D39 | ✅ adapter + heuristics + runner + `/mining-jobs`; tested offline via cassette; live async dispatch deferred |
| FR-CUR-3 | NFR-8 | validity-threats record (`curated/threats.py`) + analysis gate + paper injection | ✅ record gates analysis; injected verbatim into the paper draft |
| FR-CUR-4 | RQ-F3; FR-PROT-7 | archive/replication-package import | ✅ Phase 24 Slice B — ArchiveAdapter (MiningAdapter), registered in ADAPTERS, 6 tests with cassette fixture |
| FR-AGF-1 | FR-DASH-9; FR-META-3 | `manifest.py` + `GET /.well-known/platform-manifest` + `scripts/agent_manifest_demo.py` | ✅ manifest from documents of record; scripted demo bootstraps an agent from the URL alone |
| FR-AGF-2 | agent context steering | `scripts/generate_agents_md.py` → `AGENTS.md` + CI drift gate | ✅ generated from glossary + SRS + manifest + CLAUDE.md; `--check` goes red on drift |
| FR-AGF-3 | S6 | `data-agent` attributes + `platform/docs/agent-annotations.md` + drift lint | ✅ stable names + conventions doc; `check-agent-annotations.mjs` keeps doc↔code in sync |
| FR-ETH-1 | S3,S2 | lifecycle gates + file store | ✅ |
| FR-ETH-2 | S2,S3; C1 | all instruments | ✅ built instruments comply (sizes/shapes/timings + salted in-memory hashes only); agent-leg scoped exception under FR-AGENT-5 (`redact.py` choke point, `metadata-only` default, grep-the-output test) |
| FR-ETH-3 | S2,S3 | all components | ✅ by construction |
| FR-ETH-4 | S2,S3; NFR-5 | assistant data boundary (`assistant.py`) | ✅ no tool returns a row-level event; grep-the-output test |
| NFR-1 | S2; C2; D3 | all instruments | ✅ fire-and-forget, O(1) handlers, swallow-count-report-once |
| NFR-2 | S1 | sinks + middleware | ✅ idempotent ingest + visible seq gaps |
| NFR-3 | S6 | TERN core/adapter split | ✅ scientific logic in `src/core`, zero `vscode` imports |
| NFR-4 | S6; C4 | schema versions, recipe contract | 🔶 `protocolVersion` ✅; event `v` stored + unknown flagged |
| NFR-5 | S2,S3 | whole stack | 🔶 |
| NFR-6 | S5 | recipes, pinned deps | ✅ deterministic recipes; pinned via uv lock; replication kit reproduces `report.md` byte-for-byte |
| NFR-7 | S1 | docker compose packaging | ✅ compose + demo seed; SPA served by the middleware image, one process; `scripts/smoke.sh` green from clean `docker compose up` |
| NFR-8 | S4 | recipe statistics (`analysis/stats.py`) | ✅ every test line carries exact test, effect size, per-cell n, small-n framing |
| NFR-9 | production readiness | compose + demo seed + smoke test | ✅ `scripts/smoke.sh` green from `docker compose up -d --build` |
| NFR-10 | S4 | `build-vs-adopt.md` | ✅ decisions recorded |
| NFR-11 | S6,S7; open-source posture | README, CONTRIBUTING, RUNBOOK, TOUR, platform copy; internals → `docs/roadmap/` | 🔶 docs restructured; platform chip inversion pending |
| NFR-12 | S7; D34, D35 | design system + `platform/` app (`specs/nfr-12-experience.md`) | 🔶 token system + surfaces built + gated (tokens-only lint, both themes); browser axe/screenshot evidence pending |
| FR-INST-20 | S6,S7; platform loop | `middleware/` enrollment + `extension/` connect | ✅ mint/redeem/server-stamp verified via pytest; platform enrollment table with copy-link + deep-link + live polling; extension pairing state machine (`src/core/pairing.ts`) with 13 transition tests; pre-flight at each session start; `vscode://…/pair` URI handler; all 104 extension tests pass |
| FR-ING-7 | RQ-F1; S3 | `middleware/enrollment.py` + ingest auth | ✅ mint/list/revoke/redeem, server-stamp, never-block-never-drop, and the token/credential-never-persists grep test all pytest + live-verified |
| FR-INST-21 | wall #6; FR-PROT-4 | `middleware/` capture-config + `extension/` core | ✅ derive/version/apply-at-boundary logic pytest + `node:test` verified, including a wall-6 `shouldApplyCaptureConfig` lifecycle test (apply→mid-session-refuse→next-boundary-applies); pre-flight summary shown before every session start (not just pair); re-pull at each session boundary via `refreshConfigAtSessionStart`; `captureConfigVersion` comparison enforced server- and client-side |
| FR-INST-22 | FR-ETH-2; S6,S7 | `extension/` sidebar view container + leg surface | ⬜ Phase 25 — no `viewsContainers`/`views` in the manifest today; status bar is the only permanent UI |
| FR-DASH-10 | S1; FR-DASH-3 | `platform/` EnrollmentPanel | ✅ mint/list/revoke + streaming status + per-row capture-config visibility + copy-link + deep-link "Open in VS Code" companion + 15s live polling — all verified via build/lint; backend returns `connectionString` on list endpoint; NFR-12 browser evidence pending manual walkthrough |
| FR-DASH-11 | FR-DASH-10; FR-CONV-4/5 | `platform/` EnrollmentPanel toggle console | ✅ Phase 20: backend toggle POST/GET/catalog + FR-CONV-7 consent relevance; extension `IdeHealthCollector`; platform `TogglePopover`; pytest + build verified |
| FR-DASH-12 | FR-INST-19; wall #1/#6 | `protocol/` derive + `extension/` core | ✅ Phase 21 |
| FR-DASH-13 | FR-DASH-11; wall #1/#6 | `middleware/` `_TOGGLE_CATALOG` + `platform/` console + `extension/` leg surface | 🔶 Phase 25 Slice A built — catalog spans all four legs (`leg` field + metrics/behavioral/agent entries) and `leg_summary()` returns all four with `enabled`/`disabled`/`unavailable`; 7 pytest cases incl. omitted-leg and grounding-honesty. Remaining: platform console grouping by leg, and the IDE renderer (FR-INST-22) |

## 2. RQ → data elements → recipes (analysis coverage)

| RQ | Data elements (event types / columns) | Recipes | Status |
| -- | ------------------------------------- | ------- | ------ |
| RQ-P1 | `fatigue_response`, stuck events, debrief payloads | `fatigue-by-condition`, `stuck-episodes`, `tlx-debrief` | 🔶 pipeline proven; participant data pending |
| RQ-P2 | 9-metric columns in `function_metrics` / `file_metrics` + join keys | `code-quality-by-condition` | 🔶 pipeline proven; participant data pending |
| RQ-P3 | `clipboard_paste`, `edit_burst`(+`origin`), `editor_focus`, `file_save`, heartbeat/idle | `paste-behavior` | 🔶 pipeline proven; participant data pending |
| RQ-P4 | `ai_suggestion` lifecycle events, `visible_range`, `fatigue_response` join | `ai-review-behavior` | 🔶 pipeline proven (+ Ziegler replication); participant data pending |
| RQ-P5 | `agent_turn`, `agent_tool_call`, `agent_session_meta`, reliance-loop correlations, `task_outcome` | `agent-interaction-dynamics`, `task-outcome-by-condition` | 🔶 instrumented; fails loudly at plan validation until agent-leg data lands |
| RQ-F1 | protocol → derived configs → gate reports | derived configs + gate reports | 🔶 pipeline proven; final pass after sessions |
| RQ-F2 | requires-check failures, operational findings log (FR-META-1), setup-time log | findings log + retrospective | 🔶 pipeline proven; fills during sessions |
| RQ-F3 | replication kit re-import | reproduction test | ✅ kit reproduces `report.md` byte-for-byte from a fresh checkout |
| RQ-F4 | design conversation → grounded moves → compiled protocol | elicitation record + compiler | ✅ conversation reaches a validating protocol in-surface; determinism CI-gated |

## 3. Current build snapshot

- **Foundation (phases 01–13):** the protocol engine, the four instrument
  legs, the ingestion middleware, the analysis/recipe/report/paper pipeline,
  the knowledge layer, and the ethics/privacy controls are built and green.
- **Platform layer (phases 14–18):** projects/roles/hero (FR-PLAT), the
  conversational designer (FR-CONV-1/2/3/6) and templates (FR-TPL-1/2), the
  curated-dataset leg (FR-CUR-1/2/3), agent-friendliness (FR-AGF), and
  evolution (FR-CONV-4/5) are built; server-complete with the UI gated, with
  live-transport wiring and browser NFR-12 evidence the main remaining work.
- **Open:** FR-TPL-3/4/5, FR-LIT-10, FR-META-3, FR-INST-18/19, FR-CUR-4, and
  the FR-OPS hosting-provisioning tail.

Deviations are recorded per phase in `docs/roadmap/` and, where they touch a
requirement, in the status cell above.
