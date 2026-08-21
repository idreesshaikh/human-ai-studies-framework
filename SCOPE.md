# Scope

What PHOENIX is, what it deliberately is not, and why the boundary sits where
it does. This file exists to be cited in a design argument: if a proposed
feature is on the "not this" list, the burden is on the proposal to move the
line here first, in a commit of its own.

## The spine

PHOENIX handles **design, setup, and curation, then stops.** Five steps:

1. **Talk it through.** The researcher describes an idea; the assistant
   proposes design moves one at a time. Every move carries a real citation or
   an explicit "no source found" label — there is no third state.
2. **Compile.** Accepted moves fold deterministically into a protocol. The
   same answers always produce the same protocol, with no model involved.
3. **Run.** The protocol configures TERN on each participant's machine and
   rotates task order. Pairing links carry the consent statement and the
   capture config the researcher approved.
4. **Collect.** TERN records how participants felt, what they did, and what
   the AI did — never raw code, keystrokes, or clipboard content. Events are
   stored idempotently and flagged, never dropped.
5. **Hand off.** A dataset shaped for the design, a data dictionary, and a
   starter notebook naming the exact test to run.

Two things ride alongside the spine because they answer the fear that brings
researchers here in the first place — *getting the statistics wrong*:

- **The repertoire.** Proven designs, each binding the statistical plan it
  requires, so the test is chosen by the design rather than after the fact.
- **Recruitment planning.** The power/sensitivity curve for the study's
  planned comparison, with its assumptions stated beside the numbers.
- **The Library and its citation constellation.** The corpus is the product's
  knowledge, not background reading. A study's papers grow a graph around
  themselves from real Semantic Scholar data — what they cite, what cites
  them, what resembles them — read one relation at a time through a lens
  (earlier / later / similar work), and a suggested paper is one click from
  being in the study, which regrows the graph. This is the surface where
  "grounded in 15,000 papers" stops being a claim and becomes something a
  researcher can move through.

And one proving step: **the synthetic dry run**, which pushes simulated
participants through the real capture path so the analysis plan is tested
against data before a real session happens.

## Not this

Each of these was built and removed. They are listed so the removal reads as
a decision rather than an omission.

| Not this | Why |
| --- | --- |
| **An ethics workflow** | Approval is the university's to grant. The platform owes a participant an unmissable account of what will be captured — the consent statement at pairing — not a gate that blocked setting up a study that was already designed. |
| **Study phases and a lifecycle board** | Tracking a study across seven phases was ceremony no researcher worked through, and its gate made a compiled study impossible to actually run. |
| **Mid-study amendments** | The phase-aware amendment rules existed to serve the ethics gate. With the gate gone they guarded nothing. |
| **Live presence** | Who else is looking at the study right now changes no decision this product supports. It cost a server thread to answer. |
| **Community template contribution** | A submission queue with approve/reject moderation is a workflow for many contributors. Mining writes YAML into `templates/drafts/`; promoting one is a human reading it and committing it. |
| **An operational-findings meta-layer** | A log about the platform's own behaviour that no user in the five steps above ever reads. Integrity flags belong in the ingest response and the server log. |
| **An agent-readable platform manifest** | Nothing in the arc above consumed it. The published `/schemas/*` endpoints remain; they are used. |
| **A third role, and freezing** | Owner and member. `viewer` survives only as the demo project's internal read-only grant and is not invitable. |
| **A second chat surface** | The Library had its own grounded Q&A assistant, separate from the design conversation. Two chat boxes in one product, in two vocabularies, both apparently "the assistant". The design conversation is the one conversational surface; the Library is for reading and exploring, not asking. |
| **Ambient hero artwork** | A 579-line canvas animation behind the front page. It defended nothing and was the largest component in the app. |

## Standing constraints

- **One study family.** Human–AI developer studies. Two data paths (live and
  curated archive import). One conversation.
- **Remove the model and everything except the conversation still works.** The
  repertoire, corpus search, merge, derive-from-paper, the compiler, the
  analysis recipes, and every export run with no key configured. The design
  conversation is the one surface that genuinely needs one, and with none it
  says so plainly and proposes nothing. A scripted fallback that answered
  anyway was removed on purpose: a reply that reads as designed without being
  designed is exactly the third state the grounding rule refuses.
- **The demo study's data is synthetic** and is never presented as a finding.
- **Stack is fixed.** React 19 + Vite + Tailwind v4 + vendored shadcn/ui on
  Radix, TypeScript. Tokens are the sole source of raw values; the layout
  contract and the `data-agent` names are asserted by `platform/scripts/`,
  not by convention.
- **No invented product facts.** There are no customers, no pricing, no
  benchmarks, no adoption numbers, and no testimonials.

## Status

A master's research project, under active development. The codebase — the
protocol schema, the compiler, the verify scripts — is ground truth for what
exists and behaves. This file is ground truth for what *should*.
