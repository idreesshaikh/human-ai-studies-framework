# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Primary  -  the adopting researcher** (industry or academia), who is not the
maintainer. They arrive with a research idea, not a protocol, and need to run
their own study on human–AI software development. They are competent in their
domain and afraid of getting the statistics wrong. Their job: turn an idea into
a grounded, statistically prescribed, ethics-ready protocol without reading a
methods thesis first  -  by choosing a published, citable design rather than
reinventing methodology.

This researcher is the tiebreaker for every product decision. They stay only if
the platform demonstrably encodes real methodological knowledge, and they leave
the moment it reads as a task board in disguise.

Secondary audiences, inside a project's role model (mirrored from
`middleware/authz.py` into `platform/src/lib/capabilities.ts`): project owners
managing membership and invitations, and collaborating members contributing to
the same study. Those are the two invitable roles. `viewer` survives only as
the demo project's internal read-only grant and is never invited. Participants
never use this app  -  they meet the study inside TERN, the VS Code extension.

## Product Purpose

PHOENIX is not a general research chatbot. It is the methodologist and protocol
compiler for human–AI studies: you describe what you want to find out, it asks
the questions a methodologist would, proposes design moves that each cite a real
paper or say they do not, and compiles the moves you accept into one validated,
runnable study protocol.

That protocol then configures TERN on each participant's machine, so the study
that was designed is the study that runs.

Success: a researcher describes an idea in plain language and leaves with one
validated, versioned protocol whose design decisions are either cited into the
corpus or honestly labelled unsourced. The protocol carries the statistical
plan, the instrumentation, and the curated handoff; everything else is support
for that path.

**The boundary is recorded in [`SCOPE.md`](SCOPE.md)**, which lists what was
built and deliberately removed  -  the ethics workflow, study phases, mid-study
amendments, live presence, community submissions, the findings meta-layer, the
platform manifest, the Library's separate chat assistant, the hero's ambient
artwork. That file is the authority on where the line sits; this one records
who the product is for and what it does inside it.

## Positioning

The mechanism a neighbouring product could not truthfully copy: **accepted
design moves compile deterministically into a versioned protocol.** A general
chat tool can suggest ideas; PHOENIX turns the choices a researcher keeps into
the document that can actually configure and run a study. The conversation is
not a chat skin over a document  -  it is how the document comes to exist, and
the document stays the single record of the study. Three further
claims are structural, not marketing:

- **Grounding is a type, not a tone.** Every proposal is either cited into the
  corpus / protocol repertoire or explicitly marked unsourced. There is no third
  state, and the UI may never let one masquerade as the other.
- **The statistical plan rides with the design.** The repertoire binds each
  proven design to the exact tests, effect sizes and per-cell-n rules it
  requires. The step researchers fear most is answered by construction.
- **Remove the LLM and everything except the conversation still works.** The
  repertoire, corpus search, derive-from-paper, the compiler, the analysis
  recipes and every export run with no model configured. The design
  *conversation* is the one surface that genuinely requires one, and with no key
  it says so plainly and proposes nothing (`design_assistant.ModelUnavailable`).
  A keyword-routed fallback once answered anyway; it read as a conversation
  without being one, so it was removed on purpose. Restoring that kind of
  fallback would violate the grounding rule above  -  a scripted reply
  masquerading as a designed one is exactly the third state this product
  refuses to have.

## Operating Context

A researcher works in a browser, usually on a laptop, in a normal working
environment  -  a shared office, a lab, a home desk  -  most often in daylight or
under office light, in sittings long enough to rule on a whole sequence of
proposals.

The route through the product: the public hero (`/`), which also exposes the
repertoire without an account; sign-in (the server announces its mode via
`GET /auth/config`  -  `none`, `token` or `clerk`); a project (`/p/:slug`); a
study workspace (`/p/:slug/studies/:id`) whose tabs are **Conversation,
Library, Data, Planning, Participants**, with the compiled protocol draft in a
rail beside them. From there: participant links (`vscode://…/pair` deep links)
that install the study on a participant's editor, capture running under a
consent statement the researcher approved, and finally the curated handoff.

There are no lifecycle phases and no approval gate between designing a study
and running it. Ethics approval is the university's to grant; what the platform
owes a participant is an unmissable account of what will be captured, which is
the consent statement carried by the pairing link.

The middleware serves the built app at `/`; one process is the whole stack, so
in production the API is same-origin and `VITE_API_BASE` is empty.

The product is **design-then-run**. Once a protocol is applied it is fixed for
that run; there is no mid-study amendment flow and no live co-presence between
collaborators. Both existed and were deliberately removed (protocol evolution,
amendment banner and history, presence chips), and future work does not
reintroduce them.

## Capabilities and Constraints

Confirmed and shipping:

- **Design conversation** with streaming turns and design-move cards the
  researcher accepts or rejects one at a time.
- **Steer** (`platform/src/lib/steer.ts`), a four-stop dial at the head of the
  thread  -  checks / assists / guides / leads. It moves two real server levers:
  register (`elicitation.PROFILES`) and initiative (the design assistant's turn
  stance). The account-wide profile in Settings is the default it starts from.
  The **method never changes with it**: turning steer down buys a quieter
  colleague, never a less rigorous one, and the stance machinery enforces that
  server-side rather than merely asking the model for it.
- **Deterministic compilation** of accepted moves into protocol YAML, diffed,
  validated, and applied only on human approval.
- **Grounding** against a ~15,000-paper corpus (FTS5 index) with real confidence
  scores, citation chips, and the literature constellation.
- **Protocol repertoire**: generic proven designs (`templates/registry/`, 16 at
  time of writing) ranked common→rare, each binding its statistical plan,
  composable by merging, plus derive-from-paper. Mining writes candidates into
  `templates/drafts/`; promoting one is a human reading it and committing it,
  not a submission queue with moderation.
- **Recruitment planning**: the power/sensitivity curve for the study's planned
  comparison  -  exact two-sample t-test power across sample size, and the total n
  each plausible effect size needs to hit the target, with the model's
  assumptions stated beside the numbers.
- **Two data paths, one schema**: the live path (cognitive, behavioural,
  static-metrics and agent-capture legs) and the curated path (archive import
  adapters, with a mandatory validity-threats record).
- **Synthetic dry run** (`POST /studies/{id}/simulate`, `middleware simulate`):
  simulated participants through the real capture path, validating the analysis
  plan against data before a real session happens.
- **Projects, roles, invitations**; templates; per-study enrollment and capture
  toggles.

**Where the product stops.** PHOENIX handles design, setup and curation, then
hands off: a dataset shaped for the design, a data dictionary, and a starter
notebook carrying the exact prescribed tests (imported, never run). Executing
recipes, per-RQ reports and the paper-section draft exist as developer CLI
capability (`analysis.cli run` / `notebook` / `paper`) and are **not** a product
claim; the app must not promise in-product analysis.

Constraints that bind all future work:

- Stack is fixed: React 19 + Vite + Tailwind v4 + vendored shadcn/ui on Radix,
  TypeScript, react-router. Deliberately no state library, no data-fetching
  library, no chart library  -  charts are hand-built SVG. A new UI dependency is
  a `requirements/build-vs-adopt.md` decision, not a convenience (NFR-10).
- **Tokens are the sole source of raw values and of type sizes.**
  `platform/scripts/lint-no-raw-literals.mjs` enforces it; charts and UI must
  read as one system.
- **The layout contract is asserted by scripts**, not by convention:
  `verify-layout.mjs`, `verify-shell.mjs`, `verify-slice1.mjs`,
  `verify-library.mjs`, `verify-timeline.mjs`, `verify-constellation.mjs`,
  `verify-comparator.mjs`, `verify-protocol-path.mjs`, `check-contrast.mjs`.
  `Surface` owns one measure, one gutter, one rhythm, one scroller;
  `.split-rail` owns the workspace geometry.
- `data-agent` attribute names are a machine-readable contract
  (`scripts/check-agent-annotations.mjs`); they are not styling hooks and are
  never renamed for design reasons.
- Two data-layer patterns coexist and must not be conflated: the `Api` interface
  with an offline in-memory fallback (shell: projects, studies, members,
  invitations, enrollment, preferences) and standalone fetch clients that raise
  `OfflineError` (study workspace: conversation, Library, Data, templates).
- Light and dark from birth, explicit override, pre-paint stamp, no flash.
- One study family: human–AI developer studies. Two data paths. One
  conversation.

Undecided product facts (do not invent): the corpus provenance model is
mid-migration from a Tier A / Tier B split (`corpus_importer.py`,
`manifest.py`) to a single continuous confidence score (`matching.py`); every
provenance-tier call site moves when that lands.

## Brand Commitments

- Name **Phoenix** / PHOENIX, with the phoenix mark and wordmark in the app
  header and on the hero (`components/brand/PhoenixMark.tsx`). The mark is an
  existing asset.
- Voice: plain, methodological, unhedged. It states what is grounded and what is
  not. It never sells.
- Standing visual constraints, recorded without expansion: **rounded corners**
  (a full radius scale lives in the tokens) and a **blue-leaning accent
  palette**, with simplicity explicitly the priority over expression.
- **Steer** is a named product feature, not a setting to be redesigned away.

## Evidence on Hand

- Real corpus of ~15,000 papers with real confidence scores; real citations
  (METR 2025, Ziegler 2022 among the seeds) surfaced as grounding chips.
- Real compiled protocol YAML and real diffs; worked artifacts in
  `docs/examples/` (protocol, ethics package, dry-run report, starter notebook).
- The codebase is ground truth for what exists and behaves: the protocol schema
  and validator (`protocol/`), the compiler, the recipe catalogue (`analysis/`),
  the verify scripts.
- **The demo study's data is synthetic** and must never be presented as a
  finding. Anything shown in `demo-study` is illustrative, as is anything
  produced by `simulate`.
- Absences future work must not fabricate: no customers, no pricing, no
  benchmarks, no adoption numbers, no testimonials. The corpus size (~15,000) is
  the only quantitative claim, and it is not verifiable from the running UI  -
  state the mechanism instead unless the figure is sourced.
- Status is honest: a master's research project under active development.

## Product Principles

1. **The protocol is the document of record.** The conversation is how it comes
   to exist; the UI never lets the chat outrank the compiled draft.
2. **Grounded or unsourced, never ambiguous.** Provenance is a first-class
   visual citizen with exactly two honest states.
3. **Answer the statistics by construction.** Wherever a design appears, the
   plan it requires appears with it  -  with per-cell n and effect sizes wherever
   results appear.
4. **Teach in the empty state.** Every empty view states what will appear and
   the one action that gets it there.
5. **Credibility is the aesthetic argument.** The researcher partly judges
   whether the platform encodes real knowledge by whether it looks like someone
   who knew what they were doing built it. Beauty here is not decoration; it is
   evidence.

## Accessibility & Inclusion

WCAG 2.2 AA is non-negotiable (NFR-12), specified testably: full keyboard
operability including accept/reject on design moves and the diff review; visible
focus; 4.5:1 text contrast in both renditions (3:1 for rules and controls);
labels and roles via the Radix layer; error messages tied to their inputs;
`prefers-reduced-motion` honoured everywhere; skeletons over spinners; a
streaming affordance within 1 s. Axe clean in CI on the core flows, and
`check-contrast.mjs` in `npm run verify`.
