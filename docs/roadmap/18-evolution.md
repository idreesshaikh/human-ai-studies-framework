# Phase 18: Evolution, Amendments (+ Feedback, removed 2026-08-06)

> Self-contained: execute this file in a fresh session at the repo root.
> Read first: `docs/VISION.md`, `requirements/specs/fr-conv.md`
> §FR-CONV-4 (the requirement of record; §FR-CONV-5 documents the
> removed feedback loop for history), `docs/design/state-machines.md` §1
> (the amendment loop inside data-collection), `docs/design/sequences.md`
> §4 (the post-ethics amendment walkthrough), `docs/design/ui-motion-spec.md`
> (AmendmentBanner; the precise register rules), and
> `docs/roadmap/README.md` (walls + charter).

**Depends on:** Phase 15 complete (conversation, compiler, elicitation
record: amendments are compilations with consequences), Phase 14 (roles:
post-freeze approval is `owner`). **Satisfies:** FR-CONV-4. **Elicited:**
owner, Phase 01 rev 9 ("study ideas and instrumentation are evolved on the
fly"). **Status:** 🔶 built: amendment engine green server-side; UI built
+ gated; live transport + browser NFR-12 evidence deferred (see the
deviations log below for what shipped). This phase originally also built
FR-CONV-5 (the platform's own feedback loop: mark a turn as feedback →
finding → inert retrospective proposal, surfaced on a "Platform findings"
tab). That surface wasn't earning its keep and was removed 2026-08-06,
along with its whole capture-to-proposal pipeline; see
`requirements/specs/fr-conv.md` §FR-CONV-5 and `requirements/srs.md` for
the record. This file keeps only what's still true of the amendment loop
(Slice A); the removed feedback slices (B, C) and their mentions
elsewhere in this file are struck.

## The idea

**The study evolves:** mid-study changes are spoken in the conversation,
compiled like everything else, but routed through phase-aware amendment
rules: version-visible always, consent-gated when it matters, never
sneaky.

Non-negotiable bounds, inherited verbatim:

- **Pre-ethics, amendments are ordinary compilations** (FR-CONV-4.1):
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

## Slices

### Slice A: Phase-aware amendments (FR-CONV-4)

1. **Routing**: the compiler learns the lifecycle. Compile requests
   against a frozen protocol return an *amendment* diff: apply requires
   `owner` (FR-PLAT-2), produces `protocolVersion + 1`, an `Amendment`
   row (per `data-model.md`), and, when the deterministic
   consent-relevance rule fires, the `requires re-approval` flag.
2. **The gate**: session start for `data-collection` checks the flag;
   new sessions are refused with a plain-language reason until the
   re-approval artifact is uploaded (the existing gate-artifact
   mechanism, one more artifact type). Already-collected data stays
   readable; running sessions finish untouched (F4.1).
3. **The ethics-board delta**: from the Amendment row + diff, generate
   a human-readable amendment summary document (what changed, why,
   consent impact): the thing S1 actually sends to S3. Deterministic
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
   history as a quiet vertical list on the study page: versions,
   summaries, approvers, artifacts. No drama: evolution is normal.

### Slice D: The self-application demo (the phase proof)

Run the loop end to end on a real trial study:

1. Take the demo project's study (`sample-study-2026`, seeded in
   `evolutionStub.ts`) through a **post-ethics amendment**: add an instrument
   conversationally → caution fires (new data stream ⇒ consent-relevant)
   → owner approves → new sessions blocked → upload re-approval artifact
   → sessions resume under v(n+1). Sequence per `sequences.md` §4,
   recorded as a walkthrough.
2. The elicitation record now contains design and amendment history;
   export it and show the full chain still renders (FR-CONV-6 F6.1
   extended by amendment hunks).

## Degrees of freedom

- **Amendment-history UI anatomy**: list vs. timeline vs. rail; the
  binding parts are precise register, version chips, and
  plain-language summaries.

## Acceptance (maps to fit criteria)

- FR-CONV-4: F4.1 consent-relevant amendment blocks new sessions until
  the artifact exists, collected data stays readable; F4.2 threshold
  tweak applies next-session only (test with an in-flight fake session);
  F4.3 mixed-version sessions render distinguishably.
- FR-CONV-6 (regression): the exported elicitation record includes
  amendment decisions; redaction still never unmakes them.
- NFR-12: the amendment banner passes the standard gates; statistics and
  consent surfaces remain unanimated (the never-animate list in
  `ui-motion-spec.md` §7 explicitly covers ethics surfaces).

## Verification steps

1. `uv run pytest && uv run ruff check .`: amendment routing,
   consent-relevance rule (table-driven test: change → relevant?),
   session-start gate.
2. The slice-D walkthrough, recorded end to end (amendment + export).
3. Determinism regression: replaying the *original* conversation still
   yields a byte-identical draft (amendments must not have perturbed the
   base compiler: F3.1 stays green).
4. NFR-12 evidence archived for the new surfaces.

## Deviations log

Record departures here and in `requirements/traceability.md` §3.

- **2026-07-18: study-revision counter is separate from `protocolVersion`.**
  The spec (and FR-CONV-4.2) call the amendment counter the "protocol version";
  Phase 17 had already fixed the protocol document's `protocolVersion` field to a
  schema-shape enum `[1, 2, 3]` (v1 human, v2 curated, v3 agents). Bumping that
  field per amendment would break schema validation, so the amendment counter
  lives beside the protocol as `StudyEvolution.current_version` (a DB integer),
  stamped onto each `SessionOpen`: that integer is what the version chips
  render (F4.3). The invariant the spec cares about (drift is version-visible)
  holds; only the home of the counter moved. Prefer-the-invariant.
- **2026-07-18: new tables, never an ALTER.** Evolution state lives in new
  tables (`study_evolution`, `amendments`, `session_opens`) because the loud
  stale-DB check (`db._check_schema`) fires on a column missing from an
  *existing* table; new tables let pre-Phase 18 databases keep loading (the
  NFR-1/2 "never silent data loss" posture). (A fourth table,
  `aggregate_shapes`, backed the FR-CONV-5 feedback pipeline and was dropped
  with it on 2026-08-06.)
- **2026-07-18: evolution UI runs on a deterministic offline store.** The
  amendment banner/history are built on `platform/src/lib/evolutionStub.ts`
  exactly as the design conversation runs on `designStub.ts`: the server
  endpoints are built + tested, and wiring the transport is the same deferred
  slice the conversation surface carries (Phase 14 note). Browser NFR-12
  screenshot/axe evidence for the new surfaces is deferred with Phase 14's,
  pending a running stack; the surfaces do pass the standing NFR-12 gates
  (tokens-only lint, both-theme tokens, no raw literals, keyboard-reachable,
  unanimated consent surfaces). (This store also carried feedback
  marking/platform-findings lineage for FR-CONV-5, removed 2026-08-06.)
- **2026-07-18: instrument evolution as compiler moves.** Slice A.4 rides the
  same compile path via two new move ops on the `instruments` dict section
  (`add-instrument`: a new data stream, consent-relevant; `reconfigure`: a
  deep-set threshold tweak, not consent-relevant), applied by
  `compiler._apply_instrument_moves` after the base draft is built. The design
  assistant proposes them through the deterministic no-LLM scripts.
