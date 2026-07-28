# Phase 18 — Evolution: Amendments + Feedback

> Self-contained: execute this file in a fresh session at the repo root.
> Read first: `docs/VISION.md`, `requirements/specs/fr-conv.md`
> §FR-CONV-4/5 (the requirements of record),
> `docs/design/state-machines.md` §1 (the amendment loop inside
> data-collection), `docs/design/sequences.md` §4 (the post-ethics
> amendment walkthrough), `docs/design/ui-motion-spec.md`
> (AmendmentBanner; the precise register rules), and
> `docs/roadmap/README.md` (walls + charter).

**Depends on:** Phase 15 complete (conversation, compiler, elicitation
record — amendments are compilations with consequences), Phase 14 (roles —
post-freeze approval is `owner`; projects scope the feedback loop),
Phase 13 / FR-META-1..3 (findings log, retrospective, in-platform agents —
the machinery feedback flows into). **Satisfies:** FR-CONV-4, FR-CONV-5
(+ the FR-META extensions they name). **Elicited:** owner, Phase 01 rev 9
("study ideas and instrumentation are evolved on the fly"; "the platform
evolves from researcher feedback"). **Status:** 🔶 built — amendment engine +
feedback loop green server-side; UI built + gated; live transport + browser
NFR-12 evidence deferred (see the deviations log below for what shipped).

## The idea

Two loops close in this phase, and they are the same loop at two scales.
**The study evolves:** mid-study changes are spoken in the conversation,
compiled like everything else, but routed through phase-aware amendment
rules — version-visible always, consent-gated when it matters, never
sneaky. **The platform evolves:** researcher feedback given in
conversation becomes structured findings that feed the platform's own
retrospective and improvement proposals — the platform grows from its
users' conversations exactly as a study grows from its researcher's.
This self-application is the whole thesis made product; Phase 18 is the
phase where the platform starts eating its own cooking.

Non-negotiable bounds, inherited verbatim:

- **Pre-ethics, amendments are ordinary compilations** (FR-CONV-4.1) —
  no ceremony before ceremony is owed.
- **Post-ethics, drift is version-visible** (S3's core concern):
  compiled amendment ⇒ `protocolVersion` bump + Amendment record
  (summary, rationale, grounding, approver, timestamp). Consent-relevant
  changes gate **new** data-collection sessions until re-approval.
- **Running sessions are never touched** (NFR-1): config changes apply
  from the next session; an in-flight participant never feels a study
  evolve under them.
- **Consent-relevance is a deterministic rule, not an LLM judgment**:
  anything touching FR-ETH-2 scopes, the content policy, or introducing
  a new data stream is consent-relevant, by rule, testably.
- **Cross-project learning uses aggregates only** (FR-CONV-5.3): no
  conversation text, protocol content, or project identifiers ever
  leave a project boundary — grep-the-output enforced, like FR-ETH-4.
- **Proposals are inert** (FR-META posture): the platform drafts its own
  improvements; humans approve them; nothing self-applies.

## Slices

### Slice A — Phase-aware amendments (FR-CONV-4)

1. **Routing**: the compiler learns the lifecycle. Compile requests
   against a frozen protocol return an *amendment* diff: apply requires
   `owner` (FR-PLAT-2), produces `protocolVersion + 1`, an `Amendment`
   row (per `data-model.md`), and — when the deterministic
   consent-relevance rule fires — the `requires re-approval` flag.
2. **The gate**: session start for `data-collection` checks the flag;
   new sessions are refused with a plain-language reason until the
   re-approval artifact is uploaded (the existing gate-artifact
   mechanism, one more artifact type). Already-collected data stays
   readable; running sessions finish untouched (F4.1).
3. **The ethics-board delta**: from the Amendment row + diff, generate
   a human-readable amendment summary document (what changed, why,
   consent impact) — the thing S1 actually sends to S3. Deterministic
   generation, FR-ANA-6 style.
4. **Instrument evolution rides the same path** (F4.2): a threshold
   tweak compiles to a derived-config change (FR-PROT-4) effective next
   session; the derive command output is version-stamped.
5. **Version visibility everywhere** (F4.3): sessions record the
   `protocolVersion` they ran under (join keys already carry it);
   timeline and dataset views render version chips; two sessions under
   different versions are visually distinguishable without clicking.
6. **UI**: `AmendmentBanner` (precise register, lock glyph, "new
   sessions paused until re-approval" in plain language); the amendment
   history as a quiet vertical list on the study page — versions,
   summaries, approvers, artifacts. No drama: evolution is normal.

### Slice B — Feedback capture (FR-CONV-5.1)

1. **Marking**: any turn can be marked as platform feedback (context
   action on the turn; subtle affordance, warm register). Optionally the
   platform *offers* the marking when a turn reads as feedback — always
   confirmed, never auto-filed (detection is a freedom, marking is the
   requirement).
2. **The pipeline**: a marked turn produces a `Finding` row (FR-META-1
   pipeline) with `conversationLocus` — kind, context, the exact turns
   that motivated it. The findings dashboard card renders it (F5.1).
3. The feedback is *about the platform*, so it is platform-scoped data
   — but its `conversationLocus` points into project-scoped content;
   rendering the locus requires project membership (the boundary holds
   even for meta-data).

### Slice C — Aggregates-only learning + inert proposals (FR-CONV-5.2/5.3)

1. **Usage shapes**: an aggregation pass computes cross-project,
   anonymous shape data — which templates get chosen, which protocol
   slots most often end `unresolved`, where conversations stall
   (taxonomy seeded from `stalled-biased-confused-rca`), which design
   moves get rejected most. Aggregate tables carry **no** conversation
   text, protocol content, or project identifiers — F5.3 is a
   grep-the-output CI test over the aggregation output, mirroring
   FR-ETH-4's.
2. **The retrospective extension** (FR-META-2): the drafted proposal
   cites the findings rows and aggregate shapes it used (F5.2) —
   template improvements, new template candidates, UX defects — and
   lands as an *inert* draft for human review, exactly like every other
   platform-drafted artifact.
3. **The loop rendered**: a small "platform findings" surface showing
   feedback → finding → proposal lineage, so the self-application is
   *visible*, not just implemented (this is a demo-critical surface —
   see slice D).

### Slice D — The self-application demo (the phase proof)

Run the loop end to end on a real trial study:

1. Take the demo project's study (`sample-study-2026`, seeded in
   `evolutionStub.ts`) through a **post-ethics amendment**: add an instrument
   conversationally → caution fires (new data stream ⇒ consent-relevant)
   → owner approves → new sessions blocked → upload re-approval artifact
   → sessions resume under v(n+1). Sequence per `sequences.md` §4,
   recorded as a walkthrough.
2. During that same session, mark two turns as platform feedback → both
   appear as findings → the retrospective drafts a proposal citing them.
3. The elicitation record now contains design, amendment, and feedback
   — export it and show the full chain still renders (FR-CONV-6 F6.1
   extended by amendment hunks).

## Degrees of freedom

- **Stall-point taxonomy** — seed categories from the cited paper, then
  extend from observed data; the taxonomy is yours to grow (it's
  aggregate shape, so iteration is cheap and safe).
- **Feedback detection** — heuristic, LLM-suggested, or absent (manual
  marking alone satisfies the requirement — FR-CONV-5 is an S; don't
  gold-plate detection while anything harder is open).
- **Aggregation cadence** — on-demand, scheduled, or on-write; the
  grep-the-output test binds the *output*, not the schedule.
- **Proposal drafting** — prompt design and structure of the drafted
  proposals (they're inert; quality is iterable).
- **Amendment-history UI anatomy** — list vs. timeline vs. rail; the
  binding parts are precise register, version chips, and
  plain-language summaries.

## Acceptance (maps to fit criteria)

- FR-CONV-4: F4.1 consent-relevant amendment blocks new sessions until
  the artifact exists, collected data stays readable; F4.2 threshold
  tweak applies next-session only (test with an in-flight fake session);
  F4.3 mixed-version sessions render distinguishably.
- FR-CONV-5: F5.1 marked turn → findings row with locus → dashboard
  card; F5.2 retrospective proposal cites its findings rows; F5.3
  grep-the-output on aggregate tables.
- FR-CONV-6 (regression): the exported elicitation record includes
  amendment decisions; redaction still never unmakes them.
- NFR-12: the amendment banner and findings surfaces pass the standard
  gates; statistics and consent surfaces remain unanimated (the
  never-animate list in `ui-motion-spec.md` §7 explicitly covers ethics
  surfaces).

## Verification steps

1. `uv run pytest && uv run ruff check .` — amendment routing,
   consent-relevance rule (table-driven test: change → relevant?),
   session-start gate, aggregation grep test, findings pipeline.
2. The slice-D walkthrough, recorded end to end (amendment + feedback +
   export).
3. Determinism regression: replaying the *original* conversation still
   yields a byte-identical draft (amendments must not have perturbed the
   base compiler — F3.1 stays green).
4. NFR-12 evidence archived for the new surfaces.

## Deviations log

Record departures here and in `requirements/traceability.md` §3.

- **2026-07-18 — study-revision counter is separate from `protocolVersion`.**
  The spec (and FR-CONV-4.2) call the amendment counter the "protocol version";
  Phase 17 had already fixed the protocol document's `protocolVersion` field to a
  schema-shape enum `[1, 2, 3]` (v1 human, v2 curated, v3 agents). Bumping that
  field per amendment would break schema validation, so the amendment counter
  lives beside the protocol as `StudyEvolution.current_version` (a DB integer),
  stamped onto each `SessionOpen` — that integer is what the version chips
  render (F4.3). The invariant the spec cares about (drift is version-visible)
  holds; only the home of the counter moved. Prefer-the-invariant.
- **2026-07-18 — new tables, never an ALTER.** Evolution state lives in four
  new tables (`study_evolution`, `amendments`, `session_opens`,
  `aggregate_shapes`) because the loud stale-DB check (`db._check_schema`) fires
  on a column missing from an *existing* table; new tables let pre-Phase 18
  databases keep loading (the NFR-1/2 "never silent data loss" posture).
- **2026-07-18 — evolution UI runs on a deterministic offline store.** The
  amendment banner/history, feedback marking, and platform-findings lineage are
  built on `platform/src/lib/evolutionStub.ts` exactly as the design
  conversation runs on `designStub.ts` — the server endpoints are built +
  tested, and wiring the transport is the same deferred slice the conversation
  surface carries (Phase 14 note). Browser NFR-12 screenshot/axe evidence for the
  new surfaces is deferred with Phase 14's, pending a running stack; the surfaces
  do pass the standing NFR-12 gates (tokens-only lint, both-theme tokens, no
  raw literals, keyboard-reachable, unanimated consent surfaces).
- **2026-07-18 — instrument evolution as compiler moves.** Slice A.4 rides the
  same compile path via two new move ops on the `instruments` dict section
  (`add-instrument` — a new data stream, consent-relevant; `reconfigure` — a
  deep-set threshold tweak, not consent-relevant), applied by
  `compiler._apply_instrument_moves` after the base draft is built. The design
  assistant proposes them through the deterministic no-LLM scripts.
