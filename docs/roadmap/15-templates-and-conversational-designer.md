# Phase 15: Templates + Conversational Designer

> Self-contained: execute this file in a fresh session at the repo root.
> Read first: `docs/VISION.md` (the direction + build order),
> `requirements/specs/fr-conv.md`, `requirements/specs/fr-tpl.md`,
> `requirements/specs/fr-lit.md`, `requirements/specs/nfr-12-experience.md`,
> `docs/design/ui-motion-spec.md` (the design contract for every surface
> named here), and `requirements/build-vs-adopt.md` D34/D35/D37.

**Depends on:** Phase 02 (protocol schema + validator, the compile target),
Phase 04 (middleware, where the conversation/template endpoints mount),
Phase 10 (FTS5 corpus index + the D32 tool-use loop, grounding retrieval),
FR-LIT-8 pipeline (`scripts/corpus_harvest.py`, the corpus the importer
loads). **Satisfies:** FR-TPL-1..4, FR-CONV-1/2/3/6, FR-LIT-9, and the
FR-LIT-8 corpus importer. **Elicited:** owner, Phase 01 rev 9
("experiments are built from conversations, grounded in science") + rev
13 ("start implementing": the conversation surface is the first thing
to become real). **Status:** In progress: slices 1–4 built and tested
(the FR-CONV loop end-to-end: importer, match ladder, template registry,
server compiler + approval + elicitation record). Remaining: FR-TPL-3
form path, and two seed templates (`cursor-mining`, `hai-eval`) parked in
`templates/drafts/` until their recipes exist (Phase 16/analysis).

## The idea

The end-to-end thesis proof: **idea → conversation → grounded protocol →
prescribed statistics → report**, on the demo study, with the protocol
YAML staying the sole document of record (FR-PROT-1) and *no LLM in the
compiler* (FR-CONV-3). Templates (FR-TPL) are the knowledge the
conversation reasons over; the corpus (FR-LIT-8) is what it cites; the
compiler (deterministic) is what turns accepted design moves into
protocol diffs. The whole surface must be **fully usable with no LLM
key**: the structured designer and a deterministic demo script are the
degradation path (FR-CONV §5, NFR-4).

Non-negotiable bounds, inherited verbatim:

- **Protocol is the sole record (FR-PROT-1):** the conversation produces
  and amends protocol *drafts*; it never *is* the protocol. Everything
  downstream still derives from the YAML alone.
- **No LLM in the compile step (FR-CONV-3.1):** the LLM proposes moves;
  a pure function `(draft, acceptedMoves) → draft'` produces YAML.
  Determinism is a fit criterion (F3.1: replay → byte-identical draft).
- **Cite only what you retrieved (FR-CONV-2.2 / FR-ETH-4):** a design
  move may carry only grounding returned by its tools in that exchange;
  unsourced moves are labeled, never hidden (F2.1 grep-the-output test).
- **NFR-12 is a requirement, not a finish:** WCAG 2.2 AA, reduced-motion
  parity, both themes, streaming without layout shift, enforced per
  `ui-motion-spec.md`, every iteration a gated commit (D35).

## Sequencing: slices (each independently demoable)

Phase 15 is built in slices so the conversation has a running home early
(the build order permits the `platform/` scaffold to land here rather
than waiting for Phase 14).

### Slice 1: Platform scaffold + conversation surface (no-LLM stub) 🔶 building

The visible heart, runnable with zero backend and zero LLM key.

1. **`platform/` app scaffold** (D34/D37): Vite + React 19 + TS +
   Tailwind v4 + the vendored shadcn substrate. One design-token layer
   (`src/styles/tokens.css`) realizing `ui-motion-spec.md` §1: motion
   durations/eases, radii, the neutral+accent palette bridged to the
   dataviz tokens; light + dark; `prefers-reduced-motion` honored.
2. **Conversation components** (`ui-motion-spec.md` §2): `StreamingTurn`,
   `MoveCard` (keyboard-first `a`/`r`, 420ms fold-to-draft on accept,
   200ms exhale on reject), `GroundingChip` (tier badge A/B/study),
   `UnsourcedLabel` (dashed amber, never red), `RecommendationCard`
   (dealt-card tilt), `EmptyState`, `TierBadge`, `SlotMeter`.
3. **Deterministic design-assistant stub** (`src/lib/designStub.ts`):
   given researcher input, emits scripted platform turns + design moves +
   grounded recommendation cards. Scripts include the FR-LIT-9 F9.1 demo
   ("juniors over-trust AI code" → surfaces `trust-in-ai-code-generation`
   + `insecure-code-with-ai-assistants` with reasons). This *is* the
   no-LLM degradation path, not throwaway mock data.
4. **Client-side draft + accept/reject state**: accepting/rejecting a
   move updates a local protocol-draft model and the `SlotMeter`; the
   draft rail shows compiled-so-far YAML (client-side compiler stub
   mirroring the eventual server compiler's shape).

Slice-1 fit (demo-able without middleware): F-S1.1 the demo script runs
end to end in the browser, `npm run build` green; F-S1.2 rejecting a move
provably keeps it out of the draft rail; F-S1.3 reduced-motion on → every
surface fully functional, zero animation; F-S1.4 no raw hex/ms/px in
components (NFR-12 F1 lint), both themes pass 4.5:1.

### Slice 2: Corpus importer + real grounding (FR-LIT-8 importer, FR-LIT-9)

Load `docs/papers/corpus-index.json` + Tier A into the middleware's FTS5
index (the importer FR-LIT-8 named "pending"); replace the stub's scripted
recommendations with a real match ladder (LLM rerank → FTS → seed-graph,
FR-LIT-9). Grounding chips resolve to real corpus rows; one-click ingest
into the study paper set. Fit: F9.1/F9.2/F9.3 from `fr-lit.md`.

### Slice 3: Template registry + statistical plans (FR-TPL-1..4)

The versioned template registry + JSON Schema (sibling of the protocol
schema); seed templates (the METR RCT `metr-rct-v1`, the Ziegler
telemetry×survey `ziegler-telemetry-survey-v1`, plus `hai-eval` and
`cursor-mining` drafts) each encoding its statistical plan; the
conversation selects and parameterizes a template; the form path
(FR-TPL-3) edits the same draft. Fit: FR-TPL fit criteria.

### Slice 4: Server compilation + approval + elicitation record (FR-CONV-3/6)

Move the compiler server-side (still LLM-free, `(draft, moves) → diff`),
wire `protocol validate` + recipe `requires` pre-check on every compile,
the approval/audit table, and store the thread+moves+decisions as the
exportable elicitation artifact (FR-CONV-6 chain: turn → move → grounding
→ hunk → instrument → element → recipe → claim → paper section). LLM
provider per D32 with the FR-ETH-4 tool boundary. Fit: FR-CONV-1/2/3/6.

## Degrees of freedom

The autonomy charter in `README.md` applies; specifically free here:
component internals and hook factoring; the stub's scripted
conversations beyond the required F9.1 demo (write more, make them
charming); draft-rail presentation details within the precise register;
importer batching/progress mechanics; template YAML field ordering and
prose within the published schema; form-path (FR-TPL-3) layout anatomy.
Fixed: the walls in `README.md`, every fit criterion below, the
component inventory + signature motions of `ui-motion-spec.md` §2, and
the compiler's purity.

## Acceptance (phase-level, maps to fit criteria)

- FR-CONV-1: F1.1 empty project → validating protocol draft without
  leaving the conversation; F1.2 every change is an individual move card;
  F1.3 evasive researcher ends with named `unresolved` slots.
- FR-CONV-2: F2.1 no move cites an unretrieved source; F2.2 self-report-
  only productivity draws the METR caution; F2.3 unsourced compiles with
  `grounding: none`.
- FR-CONV-3: F3.1 replay → byte-identical draft; F3.2 schema-breaking
  move bounces back as a turn; F3.3 no diff applies without a recorded
  approval.
- FR-CONV-6: F6.1 the full chain renders for one claim, both directions.
- FR-TPL/FR-LIT-9: their spec fit criteria.

## Verification steps

- `platform/`: `npm run build` green; `npm run lint`
  (the no-raw-literal NFR-12 rule) green; the demo script runs end to end
  (slice 1 driven by `verify` skill against the running dev server).
- Python: `uv run pytest && uv run ruff check .` for the importer,
  compiler, and endpoint work (slices 2/4).
- Determinism test (F3.1) and grep-the-output grounding test (F2.1) are
  CI-gated, mirroring the FR-ETH-4 grep-the-output pattern.

## Deviations log

Record here (and in `requirements/traceability.md`) any departure from
this spec, per golden rule / execution model. Slice 1 landing the
`platform/` scaffold ahead of Phase 14 is *expected* (build order note),
not a deviation.

- **2026-07-21: the LLM seam this phase always intended went unused
  until now, discovered pre-launch.** `design_assistant.respond()` has
  accepted a `client` parameter since this phase shipped, with a docstring
  promising "the Mistral seam swaps in behind the same shape", but the
  parameter was only ever forwarded to `matching.match_papers`'s reranker,
  never to the conversation's own prose/moves. Every design-conversation
  reply, keyed or not, was the deterministic scripted assistant. Closed as
  **FR-CONV-8** (new row): `middleware/design_llm.py` is the LLM proposal
  path, wired ahead of `_pick_script` in `respond()`, retrieval-first with
  a closed per-turn candidate menu (wall #3 enforced twice), falling back
  to the unchanged scripted assistant on any failure (NFR-4/5). No change
  to `compiler.py`: wall #2's byte-identical replay guarantee is untouched
  (`test_compile_is_deterministic` still passes, unmodified). Streaming
  (FR-CONV-1's SRS text already says "streamed," aspirationally) is still
  not built: no SSE/EventSource infra exists anywhere in this codebase;
  v1 ships as a blocking call with a "thinking" UI state, streaming
  explicitly scoped out as a fast-follow, not bundled into this change.
