# Traceability matrix (living document)

Updated at the end of every mega-prompt (`docs/archive/roadmap/`). A phase is complete
only when its rows here are flipped. Status: ✅ done · 🔶 partial · ⬜ open ·
- deliberately not built (Won't / superseded).

## 1. Requirement → source → implementation

| Requirement | Traces to (RQ / stakeholder / source) | Component | Implementing phase | Status |
| ----------- | ------------------------------------- | --------- | ------------------ | ------ |
| FR-PROT-1 | RQ-F1; S1,S3,S5 | `protocol/` schema | MP-02 | ✅ |
| FR-PROT-2 | RQ-F1; S6 | `protocol/` schema | MP-02 | ✅ |
| FR-PROT-3 | RQ-F1,F2; S1,S3 | `protocol/lifecycle.py` | MP-02 | ✅ |
| FR-PROT-4 | RQ-F1; S1 | `protocol/cli.py` derive | MP-02 | ✅ |
| FR-PROT-5 | RQ-F2; S1,S4 | protocol analysis plan | MP-02 | ✅ |
| ~~FR-PROT-6~~ | superseded by FR-LIT-1/3 (2026-07-11) | - | - | - |
| FR-PROT-7 | RQ-F3; S5 | replication kit export | MP-09 | ✅ (`protocol export replication-kit`; byte-identical reproduction test) |
| FR-PROT-8 | (deferred vision) | - | - | - |
| FR-PROT-9 | RQ-A1–A3; FR-AGF fit criteria; owner elicitation 2026-07-17 | protocol schema agent-participant support; fixture `protocol/examples/context-ablation-2026.yaml` | MP-17 (to be specced) | ⬜ draft fixture written (deliberately fails v1 validation) |
| FR-INST-1 | RQ-P1; S1 | Cognitive Overlay `surveys/fatiguePrompt` | built pre-roadmap | ✅ |
| FR-INST-2 | RQ-P1; S1 | Cognitive Overlay `stuckDetector/stuckPrompt` | built pre-roadmap | ✅ |
| FR-INST-3 | RQ-P1; S1,S2 | Cognitive Overlay `session/endSurvey` | built pre-roadmap | ✅ |
| FR-INST-4 | RQ-P2; S1; metrics/docs/static_code_metrics.md | `metrics/` | MP-03 | ✅ 9/9 (cognitive complexity stub-degradable per D5) |
| FR-INST-5 | RQ-P3; S1,S2; extension/docs/developer_behavior_capture.md | Cognitive Overlay behavioral leg | MP-05 | ✅ |
| FR-INST-6 | RQ-F1; all legs | join keys in every leg | MP-03/05/12 | ✅ all four legs (overlay + behavioral MP-05, metrics MP-03, agent MP-12) |
| FR-INST-7 | (deferred vision); S6 | - | - | - |
| FR-INST-8 | RQ-P4; D2 (Tako) | overlay AI-lifecycle events | MP-05 | ✅ (public-API mechanism; blind spots in `extension/docs/adaptation-notes.md`) |
| FR-INST-9 | RQ-P4; behavior doc §visible ranges | overlay visible-range tracker | MP-05 | ✅ |
| FR-INST-10 | RQ-P3,P4 | overlay origin classifier (`src/core`) | MP-05 | ✅ |
| FR-INST-11 | RQ-P3 denominators; D4 (WakaTime) | overlay heartbeat/idle (`src/core`) | MP-05 | ✅ |
| FR-INST-12 | S2/S3; D4 | overlay capture filters | MP-05 | ✅ |
| FR-INST-13 | S2; NFR-1; "glass overlay" elicitation | overlay prompt surfaces | MP-05 (styling pass) | ✅ in-editor everywhere; debrief glass ✅; fatigue probe stays native QuickPick - no stable overlay-webview API exists (constraint documented in `extension/docs/adaptation-notes.md`) |
| FR-INST-14 | S5; replication provenance | overlay environment_snapshot event | MP-05 | ✅ |
| FR-INST-15 | RQ-P2 time series; D14 | workspace snapshotter (shadow git) | MP-12 | ✅ |
| FR-INST-16 | outcome ground truth; RQ-P1–P5 | task harness | MP-12 | ✅ |
| FR-INST-17 | RQ-P2 trajectory, RQ-P3/P4; metric-coverage.md; D14 | code-evolution derivation + `git_commit` events (snapshotter) | MP-12 | ✅ derivation + content-free `git_commit` built; churn/persistence **char-approximated** (line-level pending schema-v4 burst line ranges - deferred, below) |
| FR-INST-18 | RQ-P1/P3 struggle proxy; metric-coverage.md | overlay diagnostics/health stream | post-sprint (schema v4) | ⬜ |
| FR-INST-19 | RQ-C1–C4; arXiv:2603.14225; Martin-Lopez 2026 | comprehension-probe instrument (overlay + probe bank + chunk reference); draft `protocol/examples/comprehension-debt-2026.yaml` | v2 (phase to be assigned with the MP-15..18 specs) | ⬜ draft protocol written |
| FR-AGENT-1 | RQ-P5; S1 | agent leg event contract | MP-12 | ✅ |
| FR-AGENT-2 | RQ-P5; D13 | Claude Code hooks + transcript importer | MP-12 | ✅ |
| FR-AGENT-3 | RQ-P5; strengthens FR-INST-10 | correlation job (reliance loops + burst annotation) | MP-12 | ✅ |
| FR-AGENT-4 | S6; extension point | Copilot/generic import adapters | deferred (post-sprint) | ⬜ |
| FR-AGENT-5 | S2,S3; C1 | content-policy redactor + consent generator | MP-12 | ✅ |
| FR-ING-1 | S1; NFR-2; D3 (ActivityWatch) | `middleware/` :8000 ingest | MP-04 | ✅ |
| FR-ING-2 | NFR-2; S1 | `middleware/` | MP-04 | ✅ |
| FR-ING-3 | NFR-2; S1 | `middleware/` gap report | MP-04 | ✅ |
| FR-ING-4 | RQ-P1–P4; S1,S5 | `middleware/` dataset export | MP-04 | ✅ |
| FR-ING-5 | S3; FR-ETH-1; FR-LIT-1 | `middleware/` file store | MP-04 | ✅ |
| FR-ING-6 | RQ-F2 | `middleware/` protocol check | MP-04 | ✅ |
| FR-DASH-1 | S1 | `dashboard/` overview | MP-06 | ✅ |
| FR-DASH-2 | RQ-F1; S1,S3 | `dashboard/` lifecycle board | MP-06 | ✅ |
| FR-DASH-3 | S1; C2 | `dashboard/` live view | MP-06 | ✅ |
| FR-DASH-4 | RQ-F1; S1,S4 | `dashboard/` timeline | MP-06 | ✅ (agent lane renders when MP-12 data lands) |
| FR-DASH-5 | RQ-P2; S1 | `dashboard/` metrics view | MP-06 | ✅ |
| FR-DASH-6 | RQ-F2; S4 | `dashboard/` chips | MP-06 | ✅ |
| FR-DASH-7 | supervisor; S1; RQ-F2 | `dashboard/` task board (project manager) | MP-06 | ✅ |
| FR-DASH-8 | S1 | `dashboard/` knowledge views | MP-06 + MP-10 | ✅ graph + assistant panels built (MP-10) |
| FR-DASH-9 | S6,S7; owner onboarding gap (2026-07-12) | `dashboard/` guided tour + lexicon tooltips; middleware `/requirements` + `/glossary` | post-sprint enhancement | ✅ |
| FR-LIT-1 | S1,S5; D8 | middleware paper ingest + extraction | MP-10 | ✅ id path (S2) + PDF path (pymupdf, D21); FTS5 index |
| FR-LIT-2 | S1; D7,D8 | literature graph (S2 API + dashboard) | MP-10 | ✅ edge harvest + stub nodes + force-graph panel |
| FR-LIT-3 | RQ-F2; S4 | paper↔protocol links | MP-10 | ✅ seeded from protocol `literature:`, editable in drawer |
| FR-LIT-4 | S1,S4; D10; FR-ETH-4 | knowledge assistant (Claude API) | MP-10 | ✅ tool-use loop, cited answers, graceful without key |
| FR-LIT-5 | S5; D9 | Zotero import | MP-09 | ❌ withdrawn 2026-07-16 (owner decision; code removed, DB `zotero_key` column kept as legacy so old stores load) - was ✅ MP-09 |
| FR-ANA-1 | RQ-F3; S5,S6 | `analysis/core.py` | MP-07 | ✅ |
| FR-ANA-2 | RQ-F2 | `analysis/` requires-check | MP-07 | ✅ |
| FR-ANA-3 | RQ-P1–P4 | built-in recipes (incl. `ai-review-behavior`) | MP-07 | ✅ (agent/outcome recipes run once MP-12 data lands) |
| FR-ANA-4 | RQ-F2; S1,S4 | `analysis/` runner+report | MP-07 | ✅ |
| FR-ANA-5 | RQ-F3 | replicated-paper recipe | MP-07 / MP-09 | ✅ two cited replications: `ziegler-acceptance-rate` (MP-07) + `meyer-fragmentation` (MP-09) |
| FR-ANA-6 | S1,S4; "extract a paper" | paper-draft generator | MP-11 | ✅ MP-11 |
| FR-META-1 | RQ-F2 | operational findings log (middleware) | MP-04 + MP-11 | ✅ MP-11 (endpoints + ingest flags MP-04; facilitator findings DR-01..07 MP-08; auto-scan seq-gap/gate-block + recipe requires-fail rows + dashboard finding cards MP-11) |
| FR-META-2 | RQ-F2; D10 | retrospective (Claude-assisted, human-approved) | MP-11 | ✅ MP-11 |
| FR-OPS-1 | S6,S7; NFR-5 boundary; student-benefit cost constraint | `render.yaml` (demo, D25) + `deploy/compose.prod.yml` + `deploy/Caddyfile` (VM, D26) + `middleware/scripts/start_with_seed.sh` | post-sprint (2026-07-16) | 🔶 manifests + pipeline built; Render/Azure provisioning pending (RUNBOOK §9) |
| FR-OPS-2 | change management; RQ-F3; NFR-9 | `.github/workflows/release.yml` + `deploy.yml` (GHCR, D24) | post-sprint (2026-07-16) | 🔶 built; first tagged release pending |
| FR-OPS-3 | S6,S7; FR-PROT-4 | `release.yml` marketplace job (D27); `extension/package.json` publisher/repository | post-sprint (2026-07-16) | 🔶 built; publisher account + `VSCE_PAT` pending |
| FR-OPS-4 | D5; zero-idle-cost constraint | `.github/workflows/sonar-vm.yml` + compose `--profile sonar` | post-sprint (2026-07-16) | 🔶 workflow built; sonar VM provisioning pending |
| FR-OPS-5 | owner elicitation 2026-07-16; NFR-1 (ingest open); D29 | `middleware/auth.py` (none/token/clerk, 14 tests) + `GET /auth/config` + dashboard `SignIn.svelte` + `@clerk/clerk-js` widget (code-split, token-getter into `api.ts`) | post-sprint (2026-07-16) | ✅ code complete; live smoke on the owner's provisioned Clerk instance pending |
| FR-OPS-6 | owner elicitation 2026-07-16; D30 rev 2; D15 | dashboard `api.ts` (`VITE_API_BASE`) + `settings.cors_origins` → opt-in `CORSMiddleware` (off-by-default regression test) | post-sprint (2026-07-16) | ✅ |
| FR-OPS-7 | owner elicitation 2026-07-16; D29; FR-OPS-5 | per-user preference store keyed by Clerk identity (planned) | - | ⏳ blocked on Clerk provisioning |
| FR-LIT-6 | owner elicitation 2026-07-16 | `Knowledge.svelte` library list (select/remove) + busy spinner with plain-language wait copy | post-sprint (2026-07-16) | ✅ |
| FR-LIT-7 | owner elicitation 2026-07-16; D8 | provider seam already isolated (`semantic_scholar.get_json` + `cached_fetch`, now self-paced to 1 req/s); OpenAlex recorded as swap candidate | - | ⏳ seam ready, swap undecided |
| FR-META-3 | owner elicitation 2026-07-16; FR-META-1/2; FR-ETH-4 | in-platform scheduled agents over the FTS5 index | MP-13 (spec written 2026-07-16) | ⏳ specced, not built |
| FR-LIT-8 | owner elicitation 2026-07-17; FR-CONV-2, FR-TPL; D8, D36 | `scripts/corpus_harvest.py` + `docs/papers/corpus-index.json`/`CORPUS.md`; importer pending | pipeline 2026-07-17; importer MP-15 | 🔶 pipeline built + first run; importer pending |
| FR-LIT-9 | owner elicitation 2026-07-17; FR-CONV-2; RQ-F4 | paper matcher (FTS→LLM ladder) + recommendation cards | MP-15 (to be specced) | ⬜ |
| FR-LIT-10 | owner elicitation 2026-07-17; NFR-12; FR-LIT-4; FR-ETH-4 | living literature constellation + scoped RAG | MP-15/17 (to be specced) | ⬜ |
| FR-PLAT-1 | S7; owner elicitation 2026-07-17 | project model (middleware + dashboard) | MP-14 (to be specced) | ⬜ |
| FR-PLAT-2 | S7,S3; FR-OPS-5 | roles + server-side enforcement | MP-14 (to be specced) | ⬜ |
| FR-PLAT-3 | S7 | email invitations | MP-14 (to be specced) | ⬜ |
| FR-PLAT-4 | S7; NFR-11 | hero page + demo entry | MP-14 (to be specced) | ⬜ |
| FR-PLAT-5 | S1; NFR-7 | implicit-project fallback (`none`/`token`) | MP-14 (to be specced) | ⬜ |
| FR-TPL-1 | S7; RQ-F3; docs/papers corpus | study-template registry | MP-15 (to be specced) | ⬜ |
| FR-TPL-2 | S7; NFR-8; owner elicitation 2026-07-17; arXiv:2508.15503 | template-bound statistical plans | MP-15 (to be specced) | ⬜ |
| FR-TPL-3 | S7; RQ-F1 | guided study designer | MP-15 (to be specced) | ⬜ |
| FR-TPL-4 | RQ-F3; FR-LIT-3 | template↔paper links in knowledge layer | MP-15 (to be specced) | ⬜ |
| FR-TPL-5 | S6 | community template contract | deferred (post-v2) | ⬜ |
| FR-CONV-1 | S7; RQ-F4; owner elicitation 2026-07-17; arXiv:2507.02564, arXiv:2603.04244 | design conversation (platform/ app + middleware threads) | MP-15 (to be specced) | ⬜ |
| FR-CONV-2 | RQ-F4; FR-ETH-4 mechanism; arXiv:2312.10893 | grounding contract (cite-what-you-retrieved) | MP-15 (to be specced) | ⬜ |
| FR-CONV-3 | RQ-F1, RQ-F4; NFR-6 | deterministic move→YAML compiler + diff approval | MP-15 (to be specced) | ⬜ |
| FR-CONV-4 | S3; FR-PROT-2/3; NFR-1 | phase-aware amendment engine | MP-18 (to be specced) | ⬜ |
| FR-CONV-5 | RQ-F2; FR-META-1/2/3; arXiv:2601.22208 | in-conversation feedback → findings pipeline | MP-18 (to be specced) | ⬜ |
| FR-CONV-6 | S4; RQ-F4; C3 | elicitation record store + chain export | MP-15 (to be specced) | ⬜ |
| FR-CUR-1 | RQ-F3; FR-INST-6; arXiv:2511.04427, arXiv:2602.09185 | curated-dataset normalizer | MP-16 (to be specced) | ⬜ |
| FR-CUR-2 | S7; NFR-4; arXiv:2601.18341 | GitHub mining adapter | MP-16 (to be specced) | ⬜ |
| FR-CUR-3 | NFR-8; arXiv:2601.18345 | validity-threats record | MP-16 (to be specced) | ⬜ |
| FR-CUR-4 | RQ-F3; FR-PROT-7 | archive/replication-package import | deferred (post-v2) | ⬜ |
| FR-AGF-1 | owner elicitation 2026-07-17; FR-DASH-9; FR-META-3 | platform manifest endpoint | MP-17 (to be specced) | ⬜ |
| FR-AGF-2 | arXiv:2602.11988, arXiv:2601.20404 | generated agent context files | MP-17 (to be specced) | ⬜ |
| FR-AGF-3 | S6 | semantic UI annotations | deferred (post-v2) | ⬜ |
| FR-ETH-1 | S3,S2 | lifecycle gates + file store | MP-02 + MP-04 | ✅ (gates MP-02; file store MP-04) |
| FR-ETH-2 | S2,S3; C1 | all instruments | overlay ✅ incl. behavioral leg (MP-05); agent leg (MP-12) | ✅ built instruments comply (sizes/shapes/timings + salted in-memory hashes only; clipboard never read); agent-leg scoped exception implemented under FR-AGENT-5 (MP-12): conversation text passes one choke point (`redact.py`), default `metadata-only` stores zero text (grep-the-output test); snapshots content-free; `git_commit`/tool targets are hashes/counts, never message text or paths |
| FR-ETH-3 | S2,S3 | all components | by construction | ✅ |
| FR-ETH-4 | S2,S3; NFR-5 | assistant data boundary | MP-10 | ✅ enforced server-side in `assistant.py`: no tool returns a row-level event; grep-the-output test |
| NFR-1 | S2; C2; D3 | all instruments | overlay ✅ incl. behavioral leg (MP-05) | ✅ all sensors fire-and-forget, O(1) handlers, swallow-count-report-once; wrapper commands always delegate in `finally` |
| NFR-2 | S1 | sinks + middleware | overlay ✅; MP-04 | ✅ (idempotent ingest + visible seq gaps) |
| NFR-3 | S6; comparability | Cognitive Overlay core/adapter split | built; guarded in MP-05 (burst/origin/idle/filter/debounce logic all in `src/core`, zero `vscode` imports) | ✅ |
| NFR-4 | S6; C4 | schema versions, recipe contract | MP-02,04,07 | 🔶 overlay ✅; `protocolVersion` ✅ (MP-02); event `v` stored + unknown flagged (MP-04) |
| NFR-5 | S2,S3 | whole stack | binds MP-04,05,10 | 🔶 |
| NFR-6 | S5 | recipes, pinned deps | MP-07, MP-09 | ✅ recipes deterministic given a dataset (seeded jitter, no wall-clock in outputs); pinned via uv lock (D16, D20); replication kit reproduces `report.md` byte-for-byte and exports byte-identical archives (MP-09) |
| NFR-7 | S1 | docker compose packaging | MP-04, MP-06, MP-08 | ✅ compose + demo seed (MP-04); SPA served by the middleware image, one process (MP-06); full-stack proof `scripts/smoke.sh` green from clean `docker compose up -d --build` (MP-08) |
| NFR-8 | S4 | recipe statistics | MP-07 | ✅ enforced by construction in `analysis/stats.py` (every test line carries exact test, effect size, per-cell n, small-n framing) |
| NFR-9 | production sprint | compose + demo seed + smoke test | MP-08 (day 7) | ✅ `scripts/smoke.sh` green from `docker compose up -d --build`: health → dashboard → idempotent replay → dataset export → per-RQ report |
| NFR-10 | S4 | `build-vs-adopt.md` | MP-01 (this revision) | ✅ D1–D12 recorded |
| NFR-11 | S6,S7; open-source posture; owner elicitation 2026-07-16 | README, CONTRIBUTING, RUNBOOK, TOUR, dashboard copy; internals → `docs/archive/` | post-sprint (2026-07-16) | 🔶 docs restructured; dashboard chip inversion pending |
| NFR-12 | S7; owner elicitation 2026-07-17; D34, D35 | design system + `platform/` app (`specs/nfr-12-experience.md`) | MP-14 (to be specced), binds MP-14..18 | ⬜ |

## 2. RQ → data elements → recipes (analysis coverage)

| RQ | Data elements (event types / columns) | Recipes | Status |
| -- | ------------------------------------- | ------- | ------ |
| RQ-P1 | `fatigue_response`, stuck events, debrief payloads | `fatigue-by-condition`, `stuck-episodes`, `tlx-debrief` | 🔶 pipeline proven at dry run (both conditions); participant data pending |
| RQ-P2 | 9-metric columns in `function_metrics` / `file_metrics` + join keys | `code-quality-by-condition` | 🔶 pipeline proven at dry run; participant data pending |
| RQ-P3 | `clipboard_paste`, `edit_burst`(+`origin`), `editor_focus`, `file_save`, heartbeat/idle | `paste-behavior` | 🔶 pipeline proven at dry run; participant data pending |
| RQ-P4 | `ai_suggestion` lifecycle events, `visible_range`, `fatigue_response` join | `ai-review-behavior` | 🔶 pipeline proven at dry run (+ Ziegler replication); participant data pending |
| RQ-P5 | `agent_turn`, `agent_tool_call`, `agent_session_meta`, reliance-loop correlations, `task_outcome` | `agent-interaction-dynamics`, `task-outcome-by-condition` | ⬜ documented gap: uninstrumented until MP-12; fails loudly at plan validation (DR-07) |
| RQ-F1 | protocol → derived configs → gate reports | MP-08 dry run + findings log | 🔶 dry-run answer in `study/pilot/findings.md` §1: protocol drove everything; 3 specification leaks (DR-01/02/03); final pass after sessions |
| RQ-F2 | requires-check failures, operational findings log (FR-META-1), setup-time log | MP-08 `findings.md` + MP-11 retrospective | 🔶 dry-run evidence: RQ-P5 defect caught at plan validation pre-collection; 7 RE-classified findings; setup-time ledger fills during sessions |
| RQ-F3 | replication kit re-import | MP-09 reproduction test | ✅ kit reproduces `report.md` byte-for-byte from a fresh checkout (`protocol/tests/test_export.py` + live CLI demo on the 128-row demo dataset); "replicate studies in a standard way" is now demonstrated for our own study |

## 3. Phase completion log

Terse by design (regroup, 2026-07-17): each entry records what flipped and
any deviations; the full build narratives live in git history and
`docs/archive/roadmap/`.

| Date | Phase | Rows flipped | Notes |
| ---- | ----- | ------------ | ----- |
| 2026-07-11 | MP-01 | matrix created; pre-existing overlay work recorded ✅ | baseline |
| 2026-07-11 | MP-01 (rev 2) | added FR-INST-8–12, FR-LIT-1–5, FR-META-1–2, FR-DASH-7–8, FR-ANA-6, FR-ETH-4, NFR-9–10; superseded FR-PROT-6; NFR-10 ✅ (D1–D12) | project renamed; one-week sprint plan adopted |
| 2026-07-11 | MP-01 (rev 3) | added FR-AGENT-1–5 (+D13–D14), FR-INST-13–16, RQ-P5; FR-ETH-2 rev 2; FR-ANA-3 amended | agent-side gap elicited by Idrees; AI condition standardized on Claude Code in the integrated terminal |
| 2026-07-11 | MP-04 | FR-ING-1–6 ✅; FR-ETH-1 ✅; NFR-2 ✅; FR-META-1 🔶; NFR-4/7 🔶 | ingestion middleware, 17 API tests. Deviations: src layout over `middleware/app/`; participants validated as `P1..P<planned>` |
| 2026-07-11 | MP-01 (re-verification) | none; FR-ING-2 source strengthened | full SRS↔matrix audit: 70/70 IDs both directions; every cited ID exists |
| 2026-07-11 | MP-02 | FR-PROT-1–5 ✅; FR-ETH-1 🔶; NFR-4 🔶 | schema + lifecycle + CLI, 28 tests; derived settings verified key-for-key |
| 2026-07-11 | MP-03 | FR-INST-4 ✅ (9/9); FR-INST-6 🔶 | Deviation: capture pairing rewritten (`matches()` over `zip`) fixing metric misassignment; hand-verified |
| 2026-07-11 | repo restructure | D15 + D16 recorded | `extension/` + `metrics/` renames; uv workspace; PROJECT_GUIDE added |
| 2026-07-11 | MP-05 | FR-INST-5, 8–14 ✅; FR-ETH-2 ✅ (built instruments); NFR-1 ✅; FR-INST-6 advanced | behavioral leg, schema v3, 33 new mocked-timer tests. Deviations: wrapper commands, not command shadowing; paste-correlation outranks block-size in origin ranking; fatigue probe stays QuickPick (no overlay-webview API); acceptance ran scripted, dev-host pass advised |
| 2026-07-11 | MP-06 | FR-DASH-1–7 ✅; FR-DASH-8 🔶; NFR-7 advanced; D17–D19 | Svelte SPA, 7 views; 24 API + 20 vitest tests. Deviations: file dedup on (filename, sha256); bearer token optional; screenshots pending |
| 2026-07-12 | MP-07 | FR-ANA-1–4 ✅; FR-ANA-5 🔶; NFR-8 ✅; NFR-6 🔶; D20 | recipe contract + `stats.py` + 8 recipes + runner. Deviations: accept-rate-by-size uncomputable under schema v3 (gap stated,→MP-12); `ziegler-acceptance-rate` added to pilot plan; single-condition datasets degrade to descriptives |
| 2026-07-12 | MP-08 (in-week slice) | NFR-9 ✅; FR-META-1 advanced (DR-01..07); RQ rows → 🔶 pipeline-proven; pilot protocol frozen v1.0 | study kit + dry run PASS + post-mortem. Deviations: wire-level dry run (DR-06 gates first participant); smoke ended at report (closed post-rebase); sessions deferred post-sprint; demo-volume reset required (DR-05) |
| 2026-07-12 | MP-01 (rev 4, metric elicitation) | added FR-INST-17 (S) + FR-INST-18 (C); glossary +Churn +Persistence | LOC/churn/persistence gap elicited by Idrees; literature audit recorded in `metric-coverage.md`; no Must displaced |
| 2026-07-12 | MP-09 | FR-PROT-7 ✅; FR-LIT-5 ✅; FR-ANA-5 ✅; NFR-6 ✅; RQ-F3 ✅; D9 annotated; protocol v1.1 | byte-stable replication kit (reproduction test); Zotero import (later withdrawn); `meyer-fragmentation` second replication. Deviations: Meyer chosen over persistence/churn (schema-v3 computable); stdlib urllib; DataCite DOI canonicalization; dedicated `papers` table; local API stub for demo |
| 2026-07-12 | MP-12 | FR-AGENT-1/2/3/5 ✅; FR-INST-15/16/17 ✅ (17 char-approximated, stated); FR-ETH-2 agent exception implemented | fourth leg: one normalizer for hooks + import (idempotent reconciliation), `redact.py` content-policy choke point, shadow-git snapshotter, task harness, evolution derivation, correlate job; middleware per-`(session, source)` seq; schema v4; 47 new tests. Deviations: event naming follows shipped MP-07 consumers; extension-side schema-v4 items deferred (line-level persistence pending); correlate is a post-ingest job; `participant-git` stream separated |
| 2026-07-12 | MP-10 | FR-LIT-1/2/3/4 ✅; FR-ETH-4 ✅; FR-DASH-8 ✅; D10 annotated; +D21 +D22 | knowledge layer: S2 + PDF ingest, FTS5 index, cached citation graph, paper↔protocol links, assistant with FR-ETH-4 enforced in code (grep-the-output). Deviations: sibling multipart upload route; D10 temperature clause dropped (API 400s); hand-rolled force layout (D17); live-network demo deferred |
| 2026-07-12 | MP-11 | FR-ANA-6 ✅; FR-META-1 ✅; FR-META-2 ✅; D23 | deterministic paper export (`draft.md`/`draft.tex`/bib + `%% trace:` tags), findings auto-scan + cards, inert retrospective proposals. Deviations: tectonic over pdflatex (D23); scripted fake client for the drafted proposal; TaskBoard label-map bug found + fixed |
| 2026-07-12 | Post-rebase hardening | none; MP-08 deviation (2) closed | rebased onto metrics coverage gate (98.6%); smoke extended through paper + PDF compile; stale-DB loud-fail fix; RUNBOOK consolidated |
| 2026-07-12 | FR-DASH-9 (plain-language layer) | FR-DASH-9 ✅ (added + built same day) | live `/requirements` + `/glossary` endpoints (parsed from documents of record), TraceChip tooltips, 12-stop guided tour. No deviations |
| 2026-07-16 | MP-01 (rev 5) + FR-OPS build | added FR-OPS-1..4 (🔶: built, provisioning operator-side); +D24–D28; RUNBOOK §9 | deployment elicitation: live demo + releases + Marketplace at $0 on student-pack benefits; priorities S/C, no Must displaced |
| 2026-07-16 | MP-01 (rev 6, open-source refinement) | added NFR-11 + FR-OPS-5; +D29 D30 D31 | two-layer docs direction (product outside, IDs inside); internals → `docs/archive/`; README rewritten as front page |
| 2026-07-16 | LLM provider swap | D10 + D22 superseded by D32 | assistant/retrospective to free-tier REST providers; FR-ETH-4 boundary, cite-every-claim prompt, and degradation posture unchanged; `anthropic` removed from lockfile |
| 2026-07-16 | Dashboard theming + v0 loop | +FR-OPS-6 (✅ same day); D30 rev 2; FR-ETH-4 rev 2 (provider wording) | theme system (pre-paint stamp, reduced-motion); separate-origin `VITE_API_BASE` + opt-in CORS allow-list |
| 2026-07-16 | MP-01 (rev 7) + FR-LIT-6 build | added FR-LIT-6 (✅ same day), FR-LIT-7 ⏳, FR-OPS-7 ⏳, FR-META-3 ⏳; D32 rev 2 (Mistral-only) | "inherently smart" elicitation: visible paper library, self-paced S2 client, UI-selectable Mistral tiers; FR-OPS-7/FR-META-3/FR-LIT-7 deliberately deferred to their own specs (golden rule 6) |
| 2026-07-16 | FR-LIT-5 withdrawal | FR-LIT-5 ❌ (was ✅ MP-09); D9 withdrawn | Zotero importer removed outright (unused path, 3 env vars + desktop dependency); `zotero_key` column kept so old stores load; IDs struck, never deleted |
| 2026-07-16 | FR-OPS-5 completion | FR-OPS-5 ✅; D29 annotated; MP-13 spec written | Clerk client widget, code-split behind `/auth/config`; paste-a-token fallback preserved |
| 2026-07-16 | First v0 design-loop merge + SPA cache fix | none; +D33 | v0 branch selectively applied as fresh commits (Overview/TaskBoard/LiveSessions/Timeline); SPA served no-cache (stale-bundle fix, regression-tested) |
| 2026-07-17 | Vercel/v0 removed (D30 rev 4) + Clerk fix | none; D30 retired | Vercel cleaned from repo + workflow; FR-OPS-6 capability stays; clerk-js v6 `@clerk/ui` hotload fix |
| 2026-07-17 | MP-01 (rev 8, v2 platform re-alignment) | added S7; FR-PLAT-1..5, FR-TPL-1..5, FR-CUR-1..4, FR-AGF-1..3 (all ⬜, v2 milestone); glossary +9 v2 terms; `docs/VISION.md` written, v1 vision superseded-in-place; CLAUDE.md revamped | owner direction: multi-researcher platform; templates prescribe the statistical formulation; curated mining beside live capture; existing subsystems are the foundation. No built requirement changed status |
| 2026-07-17 | MP-01 (rev 9, conversational core) | added FR-CONV-1..6, NFR-12 (M* v2), RQ-F4; FR-TPL-3 rev 2 (conversation primary, form = review surface + no-LLM path); +D34 +D35; spec tree `requirements/specs/` created; glossary +7 terms | owner direction: the design conversation is the core interaction. Guardrails recorded: YAML protocol stays sole record (RQ-F1), compilation deterministic (NFR-6), post-ethics change version-visible (S3), FR-ETH-4 binds the design assistant |
| 2026-07-17 | MP-01 (rev 10, corpus at scale) | added FR-LIT-8 (M* v2, 🔶 pipeline built) + FR-LIT-9 (M* v2) + FR-LIT-10 (S); +D36; spec `specs/fr-lit-v2.md`; glossary +5 terms; design tree `docs/design/` created | owner direction: corpus to 1,000, two provenance tiers, nothing synthesized (every Tier-B row API-verified). Pipeline written same day; the first committed index generation landed with rev 12 |
| 2026-07-17 | MP-01 (rev 11, demonstrator-study elicitation) | added FR-PROT-9 (S) + FR-INST-19 (S), both ⬜; glossary: Participant rev 2 (agents enrollable) + Agent participant + Accepted chunk + Comprehension probe; research-questions.md Tier 3 (RQ-C1..C4, RQ-A1..A3) | two draft protocols as the v2 demonstration workload: `comprehension-debt-2026.yaml` (validates green; its 3 new recipes fail plan validation loudly until built - intended FR-ANA-2 behavior) and `context-ablation-2026.yaml` (deliberately fails v1 validation; FR-PROT-9's fit fixture). No new dependencies; no Must displaced |
| 2026-07-17 | MP-01 (rev 12, regroup pass) | none added/removed/renumbered; SRS status cells synced to this matrix (FR-INST-6/15/16/17, FR-AGENT-1/2/3/5, FR-ETH-2); FR-INST-6 ✅ here | owner-directed regroup: full v2 scope reaffirmed (no cuts; D34 stands). De-bloat: SRS preamble unified (one MoSCoW-per-milestone statement); build-vs-adopt summary table removed and superseded decisions (D9/D10/D22/D30) compressed to tombstones; this log compressed to terse entries (narratives in git history); constellation animation detail single-homed in `docs/design/ui-motion-spec.md`. Corpus harvest: first committed run of `scripts/corpus_harvest.py` (`docs/papers/CORPUS.md` + `corpus-index.json`). Accidentally staged corpus PDF unstaged (papers stay gitignored) |
