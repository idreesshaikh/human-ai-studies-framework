# The v2 roadmap — one platform, end to end

This directory is the **living roadmap**: the complete, buildable plan
for the conversational research platform, from the first pixel of the
hero page to the last byte of the replication kit. The v1 roadmap
(MP-01..13, the built engine) stays archived in `docs/archive/roadmap/`
as the historical record of code that already exists — this directory is
about what comes next, and it is written to be *executed*: every phase
below is a self-contained mega-prompt a fresh session can pick up and
build from, with enough precision to never wonder what was meant and
enough declared freedom to never get bogged down.

Read `docs/VISION.md` first. The family specs in `requirements/specs/`
are the requirements of record with numbered fit criteria; the design
tree in `docs/design/` (architecture, data model, sequences, state
machines, UI/motion) is the design contract. These phase specs sequence
all of that into buildable slices and add the implementation-level
decisions the specs left open.

## What we are building

A researcher arrives with an idea and *talks* it into a study. The
platform answers with the literature — an uncapped, quality-gated
corpus (1,000 papers as the floor) and a
registry of citable study templates — proposing design moves the
researcher accepts or rejects one card at a time. Accepted moves compile
deterministically (no LLM in the compiler) into a versioned YAML
protocol: the single document of record that configures instruments,
gates the lifecycle, prescribes the exact statistics, and emits the
report, paper draft, and replication kit. Data arrives from live
instrumented sessions (the four v1 legs) or from curated mining of
existing sources (GitHub first) through one join-key schema, so every
recipe and figure works identically on both. Mid-study, the conversation
stays open — changes flow through phase-aware amendments, visible and
consent-gated, never sneaky. And the platform listens back: researcher
feedback becomes findings that drive the platform's own evolution. The
whole thread is stored as the study's elicitation record — the idea, the
evidence, the decisions, and the study they became, navigable in both
directions.

Fully usable with **zero external services**: no LLM key → the
structured designer and FTS matching; offline → cached corpus and local
validation. The cloud makes it conversational; nothing load-bearing is
cloud-owned.

## The build order

Sequenced by proof-value per unit of engineering: the methodology core
first, shell polish after, metadata and evolution last (each one builds
on surfaces the earlier phases create).

```mermaid
flowchart LR
    MP15["MP-15\nTemplates +\nconversational designer"] --> MP16["MP-16\nCurated-dataset leg"]
    MP15 --> MP14["MP-14\nPlatform shell +\nhero"]
    MP14 --> MP17["MP-17\nAgent-friendliness"]
    MP14 --> MP18["MP-18\nEvolution"]
    MP16 -.->|cursor-mining demo| MP14
    MP15 -.->|conversation surface\nre-homes into shell| MP14
```

| Phase | Title | Satisfies | Status |
| ----- | ----- | --------- | ------ |
| [MP-15](15-templates-and-conversational-designer.md) | Templates + conversational designer | FR-TPL-1..4, FR-CONV-1/2/3/6, FR-LIT-9, FR-LIT-8 importer | 🔶 in progress — slice 1 built (platform scaffold + conversation surface, no-LLM stub) |
| [MP-16](16-curated-dataset-leg.md) | Curated-dataset leg | FR-CUR-1..3 | 🔶 built — full mine→dataset→threats→report chain green offline; live async dispatch + UI surfaces deferred |
| [MP-14](14-platform-shell.md) | Platform shell + hero | FR-PLAT-1..5, FR-OPS-5/7 completion, NFR-12 foundation | 🔶 built — backend + shell UI green; server-seeded demo + NFR-12 evidence pending |
| [MP-17](17-agent-friendliness.md) | Agent-friendliness | FR-AGF-1..3, FR-PROT-9 | ⬜ specced, ready |
| [MP-18](18-evolution.md) | Evolution: amendments + feedback | FR-CONV-4/5 (+ FR-META extensions) | ⬜ specced, ready |

Status key: ✅ done · 🔶 partial · ⬜ open. A phase is **done only when
its verification steps ran green, its row here is flipped, and its
requirement rows in `requirements/traceability.md` are flipped** —
finishing the code is not finishing the phase.

## The load-bearing walls (fixed in every phase)

These are the platform's physics. Every slice of every phase obeys them;
no degree of freedom below ever overrides them.

1. **The protocol is the sole document of record** (FR-PROT-1). The
   conversation produces and amends *drafts*; everything downstream —
   instruments, gates, analysis, paper — derives from the YAML alone.
2. **No LLM in the compile step** (FR-CONV-3). The LLM proposes; a pure
   function `(draft, acceptedMoves) → draft'` produces YAML. Replay is
   byte-identical, and that is a CI-gated test.
3. **Cite only what you retrieved** (FR-CONV-2, FR-ETH-4). A move may
   carry only grounding returned by tools in that exchange; unsourced
   moves are labeled, never hidden, and `grounding: none` is recorded in
   the compiled protocol, not just displayed.
4. **Join keys everywhere** (FR-INST-6). `participantId`, `condition`,
   `sessionId`, timestamp, schema version — on every row of every leg,
   live or mined. A source that can't provide them doesn't ship.
5. **Schema versioning, consumers branch** (FR-PROT-2, NFR-4). Any
   change to event or protocol shape bumps the version; nothing guesses.
6. **Never interrupt the participant** (NFR-1/2). Sensors and sinks are
   fire-and-forget; running sessions are never reconfigured; loss is
   detectable via `seq` gaps, never silent.
7. **Privacy by construction** (FR-ETH-2). Aggregates, shapes, salted
   hashes — no raw code, keystrokes, or identities, and mined *strangers*
   get the same protection as consented participants. The assistant sees
   papers, templates, drafts, aggregates — never row-level events, ever.
8. **Honest statistics** (NFR-8). Exact tests, effect sizes, per-cell n,
   small-n framing; never a bare p-value. Statistics never animate.
9. **Everything degrades** (NFR-4/5/7). No LLM key, no GitHub token, no
   network: the platform loses convenience, never function. One process,
   one SQLite file, `docker compose up` is the whole story; port 8000 is
   the contract.
10. **The experience bar is a requirement** (NFR-12). Both themes, WCAG
    2.2 AA, reduced-motion parity, streaming without layout shift, zero
    raw hex/ms/px in components, keyboard-complete. Every phase's
    acceptance includes its walkthrough.
11. **Glossary names win** (`requirements/glossary.md`): `participant`
    not `user`, `condition` not `group`, `recipe` not `script` — in code
    identifiers, schema fields, and UI copy alike.
12. **New dependency ⇒ decision row first** (`build-vs-adopt.md`,
    NFR-10). The substrate is decided (D34/D37: React 19 + Vite +
    Tailwind v4 + vendored shadcn; D11: SQLite; D32: Mistral REST);
    anything beyond it needs its D-row before `npm install`.

## The autonomy charter (where the builder is free)

These specs are precise about *contracts* and deliberately open about
*construction*. If you are the model executing a phase: the following
are yours to decide, without asking, as long as the walls above stand.
Use the freedom — a bogged-down builder re-reading the spec for
permission is a failure mode this section exists to kill.

- **Code structure.** Module layout, file naming, component composition,
  hook/service factoring, test organization — yours. Match the existing
  style of the package you're in; don't invent parallel patterns.
- **Interaction design within the registers.** The UI/motion spec fixes
  tokens, registers (warm/precise), the quirk budget, and the named
  signature moments. Everything else — spacing, layout grids, empty-state
  copy, hover details, how a table sorts — is yours, judged against
  "would a designer sign this?". Invent micro-moments freely within the
  quirk budget; the spec's inventory is a floor, not a ceiling.
- **Microcopy.** Voice rules are fixed (first person for platform
  actions, no IDs in UI, no exclamation marks near numbers); the words
  are yours.
- **Algorithms and internals.** Ranking weights inside the match ladder,
  debounce timings, cache shapes, pagination sizes, worker vs. main
  thread — yours, provided the fit criteria still pass and constants
  live in one named place (not sprinkled literals).
- **Slice order within a phase.** Reorder or merge slices when
  dependencies allow; record what actually happened in the tracker and
  traceability log. Landing part of a later phase early (as MP-15 slice
  1 did with the `platform/` scaffold) is expected when the build order
  note permits it.
- **Deviate with a log line, never in silence.** If a spec detail turns
  out to be wrong or a better construction exists, prefer the invariant,
  build the better thing, and record the deviation in the phase's
  deviations log + `traceability.md`. A logged deviation is good
  engineering; a silent one is a defect.
- **Propose beyond the spec.** New ideas are welcome and cheap to
  legitimize: one requirement row (with priority + rationale) and a
  traceability line, then build. The ambition ledger below is a starting
  menu, not a fence.

What is *not* free: weakening a fit criterion, adding a dependency
without a D-row, touching v1 engine invariants, skipping the
verification steps, or shipping a Must-displacing Could (rule 6:
no shell polish while methodology Musts are open).

## The proof: the trial studies

The platform is proven by running real studies through it — these are
the owner's own trial studies, not platform features:

1. **The retro-fit** — the v1 pilot re-expressed as a `metr-rct-v1`
   template instance (MP-15, FR-TPL F1.2): the platform can describe a
   study that already happened.
2. **Comprehension debt** (`protocol/examples/comprehension-debt-2026.yaml`)
   — a live-path study through conversation → template → instruments →
   report (MP-15/18 demo workload).
3. **Context ablation** (`protocol/examples/context-ablation-2026.yaml`)
   — agent participants under the task harness; the FR-PROT-9 fixture
   (MP-17).
4. **Cursor-style mining demo** — the curated path end to end on a
   committed fixture dataset (MP-16, FR-CUR F1.1).

Together they exercise every branch: live and curated, human and agent
participants, design and amendment, no-LLM and full-conversation.

## Ambition ledger (stretch — each needs its SRS row before build)

Ideas that would make the platform feel like nothing else, parked here
so they're neither lost nor smuggled in as orphan work. Any phase may
adopt one by adding its requirement row (Could unless argued otherwise)
and a traceability line first:

- **Protocol time-machine** — scrub through a study's design history;
  the diff rail replays compilations in sequence from the elicitation
  record (FR-CONV-6 data already supports it).
- **Grounding heat** — a protocol view where each line's background
  encodes how much evidence backs it; unsourced sections visibly cooler.
  The "how sure are we?" question answered at a glance.
- **Counterfactual branches** — reopen a rejected design move in a
  sandbox thread: "what would the study look like if we had said yes?"
  Compiles into a throwaway draft, never the record.
- **Replication passport** — the paper draft embeds a machine-readable
  block (kit hash, template version, corpus refs) so another platform
  instance can re-materialize the study from the PDF alone.
- **Constellation time-lapse** — replay the study's paper set growing
  over the design conversation's lifetime; the literature review as a
  30-second film.

## Execution notes

- Each phase spec is self-contained: read-first list, dependencies,
  slices, fit mapping, verification steps, deviations log. Follow it
  literally; deviations go in the log.
- Verification is never optional: `uv run pytest && uv run ruff check .`
  for Python, `npm run check` (or `npm run build && npm run lint`) in
  the touched frontend, plus the phase's named demos and the NFR-12
  walkthrough (both themes + reduced-motion, screenshots archived).
- Public-facing surfaces follow NFR-11: plain language, no requirement
  IDs. These internal specs use IDs freely — they are anchors, not
  jargon for its own sake.
