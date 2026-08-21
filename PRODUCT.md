# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Primary — S7, the adopting researcher** (industry or academia), who is not
the maintainer. They arrive at the hosted platform with a research idea, not a
protocol, and need to run their own study on human–AI software development.
Their situation: they are competent in their domain and *afraid of getting the
statistics wrong*. Their job here is to turn an idea into a grounded,
statistically prescribed, ethics-ready protocol without reading a thesis
first — by picking a published, citable design rather than reinventing
methodology. S7 is the tiebreaker for every product decision: they stay only
if the platform demonstrably encodes real methodological knowledge, and they
leave the moment it reads as a task board in disguise.

Secondary: project owners managing roles and invitations; collaborating
researchers on the same study; viewers with read-only access.

## Product Purpose

PHOENIX (Protocol for Human-Oriented Evidence, Networked Iteration &
eXperimentation) is a platform you talk to about the study you want to run,
and it talks back with the literature. Experiments are built from
conversations, grounded in published science, instrumented automatically,
analyzed with the statistics the design actually requires, and replicable by
construction.

Success: a researcher describes an idea in plain language and leaves with a
validated, versioned protocol whose every design decision is either cited into
the corpus or honestly labelled unsourced — plus the statistical plan that
design requires, and the instrumentation to collect it.

## Positioning

The mechanism a neighbouring product could not truthfully copy: **accepted
design moves compile deterministically into a versioned protocol.** The
conversation is not a chat skin over a document — it is how the document comes
to exist, and the document stays the single record of the study. Two further
claims are structural, not marketing:

- **Grounding is a type, not a tone.** Every proposal is either cited into the
  corpus / protocol repertoire or explicitly marked unsourced. There is no
  third state, and the UI may never let one masquerade as the other.
- **The statistical plan rides with the design.** The repertoire binds each
  proven design to the exact tests, effect sizes, and per-cell-n rules it
  requires. The step researchers fear most is answered by construction.
- **Remove the LLM and everything except the conversation still works.** The
  repertoire, corpus search, merge, derive-from-paper, the compiler, the
  analysis recipes, and every export run with no model configured. The design
  *conversation* is the one surface that genuinely requires one, and with no
  key it says so plainly and proposes nothing. There was once a keyword-routed
  fallback that answered anyway; it read as a conversation without being one,
  so it was removed on purpose (see `design_assistant.ModelUnavailable`).
  Restoring that kind of fallback would violate the grounding rule above —
  a scripted reply masquerading as a designed one is exactly the third state
  this product refuses to have.

## Operating Context

A researcher works in a browser, usually on a laptop, in a normal working
environment — a shared office, a lab, a home desk — most often in daylight or
under office light, in sittings long enough to rule on a whole sequence of
proposals. They arrive at the hero, sign up (Clerk), create or join a project
(owner / researcher / viewer), open the design conversation, and work through
it: rule on proposals one at a time, watch the protocol draft compile beside
them, then move through gates, ethics, and data collection into the recipes
that execute the prescribed statistics, per-RQ reports, a paper draft, and a
replication kit that someone else's kit can import back in.

The middleware serves the built app at `/`; one process is the whole stack.
Mid-study the conversation stays open: instrumentation and design evolve on
the fly, but through phase-aware amendment rules — after ethics approval,
changes are version-visible and consent-relevant ones gate until re-approved.
Fluid, never sneaky.

## Capabilities and Constraints

Confirmed and shipping:

- **Design conversation** with streaming turns, design-move cards the
  researcher accepts or rejects, and an amendment history.
- **Deterministic compilation** of accepted moves into protocol YAML, diffed,
  validated, applied only on human approval.
- **Grounding** against a ~15,000-paper corpus (FTS5 index) with real
  confidence scores, citation chips, and a living literature constellation.
- **Protocol repertoire**: generic proven designs ranked common→rare, each
  binding its statistical plan, composable by merging.
- **Two data paths, one schema**: the live path (cognitive, behavioural,
  static-metrics and agent instrument legs) and the curated path (archive
  import adapters, with a mandatory validity-threats record).
- **Projects, roles, invitations**; export / replication kit; templates;
  session timeline; per-RQ reports and figures.
- **Recruitment planning**: the power/sensitivity curve for the study's
  planned comparison — exact two-sample t-test power across sample size,
  and the total n each plausible effect size needs to reach the target,
  with the model's assumptions stated alongside the numbers.

Constraints that bind all future work:

- Stack is fixed: React 19 + Vite + Tailwind v4 + vendored shadcn/ui on Radix,
  TypeScript. No new UI dependency without a reason the vendored layer cannot
  meet.
- **Tokens are the sole source of raw values.** `scripts/lint-no-raw-literals.mjs`
  enforces it; charts and UI must read as one system.
- **The layout contract is asserted by scripts**, not by convention:
  `verify-layout.mjs`, `verify-shell.mjs`, `verify-slice1.mjs`,
  `verify-library.mjs`, `verify-timeline.mjs`, `verify-constellation.mjs`,
  `verify-evolution.mjs`. `Surface` owns one measure, one gutter, one rhythm,
  one scroller; `.split-rail` owns the workspace geometry.
- `data-agent` attribute names are a machine-readable contract
  (`scripts/check-agent-annotations.mjs`); they are not styling hooks and are
  never renamed for design reasons.
- Light and dark from birth, explicit override, pre-paint stamp, no flash.
- One study family: human–AI developer studies. Two data paths. One
  conversation.

Undecided product facts (do not invent): the corpus provenance model is
mid-migration from a Tier A / Tier B split to a single continuous confidence
score; every provenance-tier call site moves when that lands.

## Brand Commitments

- Name **Phoenix** / PHOENIX, with the phoenix mark and wordmark in the app
  header. The mark is an existing asset.
- Voice: plain, methodological, unhedged. It states what is grounded and what
  is not. It never sells.
- Binding visual constraints the owner has stated, recorded without expansion:
  **rounded corners**, a **blue-leaning palette**, and **Steer**, the dial at
  the head of the design-conversation thread (high → low) that governs how
  much the assistant drives the study-design conversation. Owner direction on
  the bar, verbatim: *"beautiful, modern, fluid, one of its kind"* — and
  simplicity is explicitly the priority over expression.

## Evidence on Hand

- Real corpus of ~15,000 papers with real confidence scores; real citations
  (METR 2025, Ziegler 2022 among the seeds) surfaced as grounding chips.
- Real compiled protocol YAML and real diffs.
- This file is the product record; the codebase itself (protocol schema,
  compiler, verify scripts) is ground truth for what exists and behaves.
- **The demo study's data is synthetic** and must never be presented as a
  finding. Anything shown in `demo-study` is illustrative.
- Absences future work must not fabricate: no customers, no pricing, no
  benchmarks, no adoption numbers, no testimonials.

## Product Principles

1. **The protocol is the document of record.** The conversation is how it comes
   to exist; the UI never lets the chat outrank the compiled draft.
2. **Grounded or unsourced, never ambiguous.** Provenance is a first-class
   visual citizen with exactly two honest states.
3. **Answer the statistics by construction.** Wherever a design appears, the
   plan it requires appears with it — with per-cell n and effect sizes wherever
   results appear.
4. **Teach in the empty state.** Every empty view states what will appear and
   the one action that gets it there.
5. **Credibility is the aesthetic argument.** S7 partly judges whether the
   platform encodes real knowledge by whether it looks like someone who knew
   what they were doing built it. Beauty here is not decoration; it is
   evidence.

## Accessibility & Inclusion

WCAG 2.2 AA is non-negotiable (NFR-12), specified testably: full keyboard
operability including accept/reject on design moves and the diff review,
visible focus,
4.5:1 text contrast in both renditions (3:1 for rules and controls),
labels/roles via the Radix layer, error messages tied to their inputs,
`prefers-reduced-motion` honoured everywhere, skeletons over spinners, and a
streaming affordance within 1 s. Axe clean in CI on the core flows.
