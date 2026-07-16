# Metric coverage - literature vs. this framework's four legs

Elicitation artifact (2026-07-12). Trigger: gap report from Idrees - "do we
capture lines of code added or commits made?" - answered here against the
metric families published human-AI developer studies actually report, then
folded back into the SRS (FR-INST-17/18 added; everything else was already
specified). Status column: ✅ captured by a built instrument · 🔶 specified,
lands with the named phase · ⬜ gap (now covered by a new requirement) ·
✋ deliberately excluded.

Grounding sources: a 2025 systematic literature review of LLM-assistant
productivity studies ([arXiv:2507.03156](https://arxiv.org/abs/2507.03156));
METR's RCT design - task time under screen recording
([arXiv:2507.09089](https://arxiv.org/abs/2507.09089)); Ziegler et al.'s
Copilot telemetry - acceptance rate + persistence
([arXiv:2205.06537](https://arxiv.org/abs/2205.06537)); Peng et al.'s
completion-time RCT ([arXiv:2302.06590](https://arxiv.org/abs/2302.06590));
the SPACE framework (Forsgren et al., ACM Queue 2021); NASA-TLX.

## 1. Human (self-report + cognitive)

| Literature metric | Ours | Where | Status |
| ----------------- | ---- | ----- | ------ |
| Workload scales (NASA-TLX etc.) | TLX-style end survey | FR-INST-3, `end_survey` | ✅ |
| In-task affect/fatigue sampling | Likert fatigue probes, pause-timed | FR-INST-1, `fatigue_response` | ✅ |
| Getting-stuck / flow breaks | stuck detector + prompt | FR-INST-2, `stuck_response` | ✅ |
| Perceived productivity / trust surveys (TAM, SPACE-S) | debrief covers workload only; perceived-productivity items are a protocol/survey change, not code | end-survey payload is schema-free - add items in the task briefing docs | 🔶 pilot decision |
| Physiological (eye-tracking, EEG) | - | out of scope, argued in SRS Won'ts | ✋ |

## 2. Code (product + evolution)

| Literature metric | Ours | Where | Status |
| ----------------- | ---- | ----- | ------ |
| Static complexity / quality | 9-metric cognitive-load matrix | FR-INST-4 (MP-03) | ✅ |
| Quality as time series | metrics over snapshot series | FR-INST-15 (MP-12) | ✅ |
| Correctness / tests passing, time-to-first-green | task harness outcomes | FR-INST-16 (MP-12) | ✅ |
| **LOC added/deleted (gross, net, over time)** | per-burst `charsAdded/charsDeleted/linesTouched` existed; session-level series **was a gap** | **FR-INST-17** ← snapshot diffs (`insertions`/`deletions` in the `workspace_snapshot` series) | ✅ MP-12 |
| **Commits made (participant's own)** | **was a gap** (shadow git deliberately ignores participant git use) | **FR-INST-17** `git_commit` events (content-free) | ✅ MP-12 |
| **Churn (added-then-reworked in session)** | **was a gap** | **FR-INST-17** derived from snapshot series | ✅ MP-12 |
| **AI-code persistence (Ziegler's 2nd measure)** | **was a gap**; needs burst line ranges (schema v4, with the DR-01 fix) | **FR-INST-17** = origin-classified bursts × final diff | ✅ MP-12 (char-approx; line-level pending schema-v4 burst ranges) |
| Defect density / code smells post-hoc | derivable offline from snapshots + harness; no new instrument | recipe-level, MP-09 candidate | 🔶 recipe |

## 3. IDE / behavioral

| Literature metric | Ours | Where | Status |
| ----------------- | ---- | ----- | ------ |
| Suggestion acceptance rate | AI-completion lifecycle | FR-INST-8; `ziegler-acceptance-rate` recipe | ✅ |
| Review latency, scroll coverage | visible ranges + lifecycle join | FR-INST-8/9, `ai-review-behavior` | ✅ |
| Edit provenance (human/AI/paste mix) | origin classifier | FR-INST-10 | ✅ |
| Paste behavior | sizes/frequency, never content | FR-INST-5 | ✅ |
| Active vs idle time (honest denominators) | heartbeat/idle machine | FR-INST-11 | ✅ |
| Task/window switching, focus | file/window focus events | FR-INST-5 | ✅ |
| Task completion time (METR/Peng's primary) | session clock + harness first-green | FR-INST-3 + FR-INST-16 | ✅/🔶 |
| Keystroke counts | - | excluded by FR-ETH-2 (aggregated bursts carry the signal) | ✋ |
| **Error/diagnostics trajectory, build/test invocations** | **was a gap** | **FR-INST-18** (Could; schema v4) | ⬜→specified |
| Screen recording (METR's labeling source) | - | out of scope: privacy posture (S2/S3), labeling cost | ✋ |

## 4. Agent

| Literature metric | Ours | Where | Status |
| ----------------- | ---- | ----- | ------ |
| Prompt counts / turn cadence, sizes | `agent_turn` chars + timing | FR-AGENT-1 (MP-12) | ✅ |
| Tool-call mix, durations | `tool_call` (field `tool`; see MP-12 naming deviation) | FR-AGENT-1 (MP-12) | ✅ |
| Reliance/delegation patterns | derived `reliance_loop` spans | FR-AGENT-3 (MP-12) | ✅ |
| Model/config provenance | `agent_session_meta` + env snapshot | FR-AGENT-1, FR-INST-14 | ✅/🔶 |
| Token usage / cost | transcript JSONL carries usage metadata → importer lifts it into `agent_turn` (`inputTokens`/`outputTokens`) | FR-AGENT-2 | ✅ |
| Conversation content analysis | governed by content policy; pilot = `metadata-only` | FR-AGENT-5 | ✋ by consent design |

## 5. Economic / team-scale (SPACE C&E, DORA, PR throughput)

Deliberately out of scope: the unit of study is a session, not a team or a
release pipeline. PRs, deployments, lead time, and org-level SPACE
dimensions don't exist inside a 45-minute lab task. The SRS Won'ts and
scope-discipline section already argue this; recorded here so the decision
is visible next to the metrics it excludes.

## Follow-ups created from this review

- FR-INST-17 (S) + FR-INST-18 (C) in the SRS; traceability rows added.
- MP-12 spec extended: `git_commit` event, persistence/churn derivation,
  schema-v4 items (suggestion size at `shown` - DR-01 - and burst line
  ranges), token usage lift in the transcript importer.
- MP-09 second-recipe candidates named: Ziegler **persistence** or
  GitClear-style churn - both become computable once FR-INST-17 lands.
- Glossary: **Churn**, **Persistence** added.
