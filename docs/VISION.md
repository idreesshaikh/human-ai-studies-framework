# Vision: the conversational research platform

**PHOENIX** (Protocol for Human-Oriented Evidence, Networked Iteration &
eXperimentation): Framework for Conducting Human-AI Studies. Requirements:
`requirements/srs.md` (families indexed there, each with a detailed spec in
`requirements/specs/`); elicitations logged in `requirements/traceability.md`;
the phase plan in `docs/roadmap/`.

## One line

*A platform you talk to about the study you want to run, and it talks
back with the literature: experiments are built from conversations,
grounded in published science, instrumented automatically, analyzed with
the statistics the design actually requires, and replicable by
construction.*

## The core interaction

A researcher arrives with an idea, not a protocol. They open a **design
conversation** and describe what they want to know. The platform
(holding the 15,000+-paper corpus, the ranked protocol repertoire, and the
protocol schema) converses the idea into a study:

- It asks the follow-up questions a methodologist would ask.
- It proposes **design moves** (add this RQ, use this design, measure
  this, instrument that), each one a card the researcher accepts or
  rejects, each one **grounded**: cited into the corpus and templates,
  or honestly labeled unsourced.
- It pushes back with evidence ("you're proposing self-report
  productivity alone; the METR RCT found developers believed they were
  20% faster while being 19% slower").
- Accepted moves **compile deterministically** into a protocol draft:
  YAML, diffed, validated, applied only on human approval. The protocol
  remains the single document of record; the conversation is how it
  comes to exist.
- Mid-study, the conversation stays open: instrumentation and design
  evolve **on the fly**, but through phase-aware amendment rules: after
  ethics approval, changes are version-visible and consent-relevant ones
  gate until re-approved. Fluid, never sneaky.
- The whole thread (turns, moves, groundings, decisions) is stored as
  the study's **elicitation record**: the study's full decision trail
  now starts at the idea, not the spec.

And the platform listens the other way too: researcher feedback given in
conversation becomes structured findings that feed the platform's own
retrospective and in-platform agents: **the platform evolves from its
users' conversations** exactly as a study evolves from its researcher's.
That self-application is the thesis made product.

## What feeds the conversation

1. **The corpus**: quality-first and uncapped (15,000+ papers), grown by
   quality-gated, API-verifiable citation snowballing
   (`scripts/corpus_harvest.py`, refreshable as the literature moves;
   agentic discovery sources join later behind the same quality gate,
   D36). Currently built as two provenance tiers: **Tier A** (hand-curated
   seeds, each with a curator-written "why", `docs/papers/README.md`) and
   **Tier B** (pipeline-harvested via citation snowballing from Tier A, each
   carrying its own quality metrics: citations, venue, freshness, seed
   connectivity). **Adopted as the target model** (D43,
   `requirements/build-vs-adopt.md`), not yet built: a single continuous
   quality-gated **confidence** score replacing the tier split
   (`docs/design/corpus-quality-model-proposal.md`); every provenance-tier
   call site moves when this lands. Papers are *matched to the researcher's
   idea* as the conversation unfolds (FR-LIT-9), ranked by confidence,
   keyword relevance, and semantic meaning, surfaced in a live recommender
   beside the conversation and explorable as a **living literature
   constellation** (FR-LIT-10).
2. **The protocol repertoire**, not paper-replicas: **generic, proven
   study designs ranked common→rare**, each binding the **statistical plan**
   its design requires (exact tests, effect sizes, per-cell-n rules) and
   citing the many papers that used it as *references* (gated by confidence),
   **composable by merging** into something novel-but-grounded. The single
   most researcher-frustrating step ("which statistical formulation?") is
   answered by construction.
3. **Two data paths, one schema.** Does the dataset exist?
   *No* → live path: the four instrument legs (cognitive, behavioral,
   static metrics, agent).
   *Yes* → curated path: mining adapters (archive import) normalize
   external data into the same join-key timeline, with a mandatory
   validity-threats record.
   Every recipe, report, figure, and paper draft works on both.

## What the platform is not

- **Not a task board.** Project management appears only where it falls
  out of the protocol (the self-computing status view).
- **Not an Overleaf or Zotero competitor.** We emit paper drafts and
  consume paper metadata at the boundaries; writing and reference
  management stay where they are.
- **Not a chatbot skin.** The conversation's output is a validated,
  versioned, traceable protocol; remove the LLM entirely and the
  platform still works through the structured designer (the no-key
  degradation path is a requirement, not an accident).

## The surface (D34/D35, NFR-12)

The surface is a **React 19 + Vite + Tailwind + shadcn/ui** app
(`platform/`): hero page, sign-up (Clerk), projects with owner-managed
roles and invitations, the conversation + review surfaces, and the
study workspace (the design conversation plus Library, Data, and
Lifecycle tabs), held to a product bar specified testably in
`requirements/specs/nfr-12-experience.md` (one token system across UI
and charts, both themes, motion that communicates, streaming everywhere,
WCAG 2.2 AA, keyboard-complete). Designed *with Claude* in-repo (D35);
every iteration is a gated commit. The middleware serves the built app at
`/`: one process is the whole stack (NFR-7).

## The platform loop (the adopting researcher's journey)

Arrive (hero, live demo one click away) → sign up → create or join a
project (roles: owner/researcher/viewer) → open the design conversation
→ idea becomes grounded, statistically sound protocol → gates, ethics,
data (live sessions or mining runs) → recipes execute the prescribed
statistics → honest, beautiful, per-RQ reports → paper draft +
replication kit out, and someone else's kit imports back in. The loop
closes; the conversation records how it all happened.

## How the platform is built

Each capability rests on a mechanism already in the codebase:

| Capability | Built on | Status |
| --- | --- | --- |
| Design conversation | Assistant tool-loop + FR-ETH-4 boundary (FR-LIT-4) | ✅ |
| Compilation | Protocol schema + validate + derive (FR-PROT-1..4) | ✅ |
| Statistical plans | Recipe contract + `analysis/stats.py` honesty | ✅ |
| Grounding | FTS5 paper index, citation chips, literature graph | ✅ |
| Curated path | Join-key event schema + per-source streams | ✅ |
| Live path | Four instrument legs, middleware, task harness | ✅ |
| Identity | FR-OPS-5 pluggable auth + Clerk (provisioned) | 🔶 |
| Feedback evolution | Findings log + retrospective + in-platform agents | ✅/⏳ |
| Agent metadata | `/requirements` + `/glossary` live endpoints | ✅ |

## Build order

By thesis proof value per unit of engineering, the platform layer
(phases 14–18) builds on the foundation (phases 01–13):

1. **Phase 15: templates + conversational designer** (FR-TPL-1..4,
   FR-CONV-1/2/3/6): the end-to-end proof: idea → conversation →
   grounded protocol → prescribed statistics → report, on the demo
   study. Includes the retro-fit proof: our own pilot expressed as a
   template instance.
2. **Phase 16: curated-dataset leg** (FR-CUR-1..3): the Cursor-style
   template becomes runnable; the dataset-exists branch is real.
3. **Phase 14: platform shell + surface bootstrap** (FR-PLAT-1..5,
   NFR-12 foundation): projects, roles, invitations, hero, the
   `platform/` app the conversation lives in.
4. **Phase 17: agent-friendliness** (FR-AGF-1..3): manifest + generated
   context files + agent-participant protocol support.
5. **Phase 18: evolution** (FR-CONV-4/5): phase-aware amendments +
   feedback-driven platform improvement.

## Scope discipline, restated

One study family (human-AI developer studies), two data paths, one
conversation. MoSCoW against the current milestone; the traceability
spine is the first deliverable of every phase. Every invariant (join
keys everywhere, schema versioning, never interrupt the participant,
privacy by construction, honest statistics, the protocol as sole document
of record) binds every feature identically. The conversation makes the
platform feel alive; the invariants keep it science.
