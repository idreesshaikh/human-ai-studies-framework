# Vision v2 — the conversational research platform

**Framework for Conducting Human-AI Studies** — v2 direction, adopted
2026-07-17 (rev 2 same day: the conversational core). Supersedes the v1
sprint vision (`docs/archive/roadmap/00-VISION.md`, kept intact as the
record of the built foundation). Requirements: `requirements/srs.md`
families FR-PLAT, FR-TPL, FR-CONV, FR-CUR, FR-AGF + NFR-12, each with a
detailed spec in `requirements/specs/`; elicitations logged in
`requirements/traceability.md` §3 (MP-01 rev 8 + rev 9).

## One line

*A platform you talk to about the study you want to run — and it talks
back with the literature: experiments are built from conversations,
grounded in published science, instrumented automatically, analyzed with
the statistics the design actually requires, and replicable by
construction.*

## The core interaction

A researcher arrives with an idea, not a protocol. They open a **design
conversation** and describe what they want to know. The platform —
holding the 58-paper corpus, the study-template registry, and the
protocol schema — converses the idea into a study:

- It asks the follow-up questions a methodologist would ask.
- It proposes **design moves** — add this RQ, use this design, measure
  this, instrument that — each one a card the researcher accepts or
  rejects, each one **grounded**: cited into the corpus and templates,
  or honestly labeled unsourced.
- It pushes back with evidence ("you're proposing self-report
  productivity alone — the METR RCT found developers believed they were
  20% faster while being 19% slower").
- Accepted moves **compile deterministically** into a protocol draft —
  YAML, diffed, validated, applied only on human approval. The protocol
  remains the single document of record; the conversation is how it
  comes to exist.
- Mid-study, the conversation stays open: instrumentation and design
  evolve **on the fly**, but through phase-aware amendment rules — after
  ethics approval, changes are version-visible and consent-relevant ones
  gate until re-approved. Fluid, never sneaky.
- The whole thread — turns, moves, groundings, decisions — is stored as
  the study's **elicitation record**: the requirements-engineering chain
  now starts at the idea, not the spec.

And the platform listens the other way too: researcher feedback given in
conversation becomes structured findings that feed the platform's own
retrospective and in-platform agents — **the platform evolves from its
users' conversations** exactly as a study evolves from its researcher's.
That self-application is the thesis made product.

## What feeds the conversation

1. **The corpus** — 1,000 papers in two provenance tiers (FR-LIT-8):
   58 hand-curated seeds (`docs/papers/README.md`) plus a harvested,
   quality-gated, API-verifiable extension grown by citation snowballing
   (`scripts/corpus_harvest.py`, refreshable as the literature moves;
   agentic discovery sources join later behind the same quality gate,
   D36). Papers are *matched to the researcher's idea* as the
   conversation unfolds (FR-LIT-9) and explorable as a **living
   literature constellation** that doubles as the scoped
   "talk to your papers" RAG surface (FR-LIT-10).
2. **The template registry** — citable encodings of published designs
   (METR RCT, Ziegler telemetry×survey, HAI-Eval synergy, Cursor-style
   mining), each binding the **statistical plan** its design requires:
   exact tests, effect sizes, per-cell-n rules. The single most
   researcher-frustrating step — "which statistical formulation?" —
   is answered by construction.
3. **Two data paths, one schema.** Does the dataset exist?
   *No* → live path: the four instrument legs (cognitive, behavioral,
   static metrics, agent) — the built v1 engine.
   *Yes* → curated path: mining adapters (GitHub first) normalize
   external data into the same join-key timeline, with a mandatory
   validity-threats record.
   Every recipe, report, figure, and paper draft works on both.

## What the platform is not

- **Not a task board.** Project management appears only where it falls
  out of the protocol (the self-computing task board).
- **Not an Overleaf or Zotero competitor.** We emit paper drafts and
  consume paper metadata at the boundaries; writing and reference
  management stay where they are.
- **Not a chatbot skin.** The conversation's output is a validated,
  versioned, traceable protocol — remove the LLM entirely and the
  platform still works through the structured designer (the no-key
  degradation path is a requirement, not an accident).

## The surface (D34/D35, NFR-12)

The v2 surface is a new **React 19 + Vite + Tailwind + shadcn/ui** app
(`platform/`): hero page, sign-up (Clerk), projects with owner-managed
roles and invitations, the conversation + review surfaces, and the
knowledge views — held to a product bar specified testably in
`requirements/specs/nfr-12-experience.md` (one token system across UI
and charts, both themes, motion that communicates, streaming everywhere,
WCAG 2.2 AA, keyboard-complete). Designed *with Claude* in-repo (D35);
every iteration is a gated commit. The built Svelte dashboard stays as
the maintained-frozen v1 operational console until the v2 surface
reaches parity view-by-view — no big-bang rewrite of working software.

## The platform loop (S7's journey)

Arrive (hero, live demo one click away) → sign up → create or join a
project (roles: owner/researcher/viewer) → open the design conversation
→ idea becomes grounded, statistically sound protocol → gates, ethics,
data (live sessions or mining runs) → recipes execute the prescribed
statistics → honest, beautiful, per-RQ reports → paper draft +
replication kit out — and someone else's kit imports back in. The loop
closes; the conversation records how it all happened.

## Why the v1 engine survives intact

| v2 concept | Built on | Status |
| --- | --- | --- |
| Design conversation | Assistant tool-loop + FR-ETH-4 boundary (FR-LIT-4) | engine ✅ |
| Compilation | Protocol schema + validate + derive (FR-PROT-1..4) | engine ✅ |
| Statistical plans | Recipe contract + `analysis/stats.py` honesty | engine ✅ |
| Grounding | FTS5 paper index, citation chips, literature graph | engine ✅ |
| Curated path | Join-key event schema + per-source streams (MP-12) | engine ✅ |
| Live path | Four instrument legs, middleware, task harness | engine ✅ |
| Identity | FR-OPS-5 pluggable auth + Clerk (provisioned) | partial 🔶 |
| Feedback evolution | Findings log + retrospective + MP-13 agents | engine ✅/⏳ |
| Agent metadata | `/requirements` + `/glossary` live endpoints | seed ✅ |

## Build order (phases to be specced before code)

By thesis proof value per unit of engineering:

1. **MP-15 — templates + conversational designer** (FR-TPL-1..4,
   FR-CONV-1/2/3/6): the end-to-end proof — idea → conversation →
   grounded protocol → prescribed statistics → report, on the demo
   study. Includes the retro-fit proof: our own pilot expressed as a
   template instance.
2. **MP-16 — curated-dataset leg** (FR-CUR-1..3): the Cursor-style
   template becomes runnable; the dataset-exists branch is real.
3. **MP-14 — platform shell + v2 surface bootstrap** (FR-PLAT-1..5,
   NFR-12 foundation): projects, roles, invitations, hero, the
   `platform/` app scaffold the conversation lives in. *(Note: the
   `platform/` scaffold itself may land first inside MP-15 if the
   conversation needs a home before the shell — the specs allow either
   sequencing; the traceability log records what actually happened.)*
4. **MP-17 — agent-friendliness** (FR-AGF-1..2): manifest + generated
   context files.
5. **MP-18 — evolution** (FR-CONV-4/5): phase-aware amendments +
   feedback-driven platform improvement.

## Scope discipline, restated

One study family (human-AI developer studies), two data paths, one
conversation. MoSCoW against the v2 milestone; the graded RE spine is
the first deliverable of every phase. Every v1 invariant — join keys
everywhere, schema versioning, never interrupt the participant, privacy
by construction, honest statistics, the protocol as sole document of
record — binds every v2 feature identically. The conversation makes the
platform feel alive; the invariants keep it science.
