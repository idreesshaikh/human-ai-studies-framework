# FR-CONV — Conversational study design (detailed specification)

**SRS family:** FR-CONV (index rows in `../srs.md`). **Phases:** MP-15
(FR-CONV-1/2/3/6), MP-18 (FR-CONV-4/5). **Spec v1, 2026-07-17** (MP-01
rev 9 elicitation: "experiments are built from conversations; study ideas
and instrumentation are evolved on the fly; ideas are grounded in
science").

## 1. Context

The platform's core interaction is a **design conversation**: a researcher
talks to the platform about what they want to study, and the platform —
grounded in the 1,000+-paper corpus and the template registry — converses the
idea into a valid, citable, statistically sound study protocol. This is
requirements elicitation *performed by the platform*: the thesis claim
"a study protocol is a requirements specification" gains its natural
elicitation front-end (LLMREI, `llmrei-requirements-elicitation`, shows
LLM-led elicitation interviews are viable; FeedAIde,
`feedaide-feedback-reports`, shows context-aware follow-up questions
produce richer requirements than forms).

The conversation is **not a chatbot bolted onto a form**. The ordering is
inverted: conversation is the primary surface; structured views (the
template parameter form, the protocol diff, the lifecycle board) are
*review surfaces* the conversation produces and updates. A researcher who
prefers forms can still use them directly (FR-TPL-3) — the two surfaces
edit the same protocol draft.

Non-negotiable guardrails, inherited from v1:

- The **protocol (YAML) remains the single document of record**
  (FR-PROT-1). Conversation produces and amends protocol drafts; it never
  *is* the protocol. Everything downstream (instruments, gates, analysis)
  continues to derive from the protocol alone.
- The lifecycle governs change: after ethics approval, conversational
  amendments route through the amendment mechanism (§FR-CONV-4), never
  silently (S3's core concern).
- FR-ETH-4 binds: the design assistant sees papers, templates, protocol
  drafts, and aggregate summaries — never row-level participant events.

## 2. Definitions

- **Design conversation** — the persistent, per-study thread between
  researcher(s) and the platform in which a study is elicited, designed,
  and evolved. One study : one conversation (it spans phases).
- **Design move** — one platform-proposed change to the protocol draft
  (add an RQ, choose a template, set a parameter, add an instrument,
  amend a threshold), carried as a structured object alongside the prose
  turn, individually acceptable/rejectable.
- **Grounding** — the citation set attached to a design move: paper refs
  (corpus/knowledge base), template IDs, or SRS/glossary anchors.
  Ungrounded moves are visibly labeled `unsourced — needs your judgment`.
- **Compilation** — deterministic translation of accepted design moves
  into a protocol draft diff (YAML), shown as a diff, applied only on
  researcher approval.

## 3. Requirements detail

### FR-CONV-1 (M, v2) — The design conversation

Every study SHALL have a persistent design conversation from before the
study exists (project-level "new study" thread) through write-up.

Elaboration:
1. The conversation elicits, in adaptive order (not a fixed script):
   research goal → candidate RQs → population/participants → design
   choice (template selection or bespoke) → conditions → dataset-exists
   branch (live instrumentation vs. curated data, FR-CUR) → measures and
   instruments → session plan → ethics posture → statistical plan
   (FR-TPL-2). The platform asks follow-up questions when a slot is
   ambiguous or empty (FeedAIde pattern), and challenges choices that
   conflict with evidence (e.g. proposing self-report productivity alone
   triggers the METR perception-gap caution,
   `metr-early-2025-dev-productivity`).
2. Multi-user: any project `researcher`+ may contribute turns; the
   conversation shows attribution per turn. Compilation approval requires
   a role ≥ `researcher`; protocol *freeze* requires `owner` (FR-PLAT-2).
3. Streaming responses; interruptible; every platform turn that proposes
   changes carries its design moves as structured payloads (§2), rendered
   as accept/reject cards inline in the thread.
4. The conversation is resumable across sessions and devices with full
   context (server-side thread storage, FR-PLAT-1 project scoping).

Fit criteria:
- F1.1 Starting from an empty project, a researcher reaches a
  protocol draft that passes `protocol validate` **without ever leaving
  the conversation surface** (demo-able end-to-end).
- F1.2 Every platform-proposed protocol change in that walkthrough is
  individually visible as a design move card; rejecting one provably
  keeps it out of the compiled draft.
- F1.3 The elicitation covers all mandatory protocol sections
  (FR-PROT-1's list); a deliberately evasive researcher ends with
  explicit `unresolved` slots named by the platform, not silent gaps.

### FR-CONV-2 (M, v2) — Grounding: ideas anchored in science

Every design move SHALL carry grounding (§2) or be visibly labeled
unsourced.

Elaboration:
1. Grounding resolves against: the study's paper set + the platform
   corpus index (FTS5, FR-LIT-1), the template registry (FR-TPL-1), and
   the requirements/glossary endpoints (FR-DASH-9). Citations render as
   the knowledge layer's clickable chips; a cited paper not yet in the
   project's paper set offers one-click ingest (FR-LIT-2 flow).
2. Grounding is *retrieved, then claimed* — the assistant may only cite
   sources returned by its tools in that exchange (the FR-ETH-4/FR-LIT-4
   cite-what-you-retrieved mechanism, already enforced server-side).
3. Contrarian grounding is a feature: when the corpus contains evidence
   *against* a researcher's choice, the platform surfaces it (e.g.
   benchmark-score-only evaluation → `realhumaneval`'s benchmark ≠ human
   utility finding; unvalidated agent metrics → `ai-agents-that-matter`).
4. The grounding vocabulary of study strategy (lab/field/sample) follows
   Stol & Fitzgerald's ABC framework (corpus index §Not downloaded) via
   the glossary once ingested.

Fit criteria:
- F2.1 Grep-the-output style test: no design move in a recorded
  compilation session carries a citation absent from that exchange's tool
  returns.
- F2.2 A scripted conversation proposing "measure productivity by
  self-report only" receives a grounded caution citing the METR paper.
- F2.3 Unsourced moves render with the `unsourced` label in the UI and
  compile into the protocol with a `grounding: none` annotation —
  honesty is recorded, not just displayed.

### FR-CONV-3 (M, v2) — Compilation: conversation → protocol, human-approved

Accepted design moves SHALL compile deterministically into a protocol
draft diff, presented as a diff, applied only on explicit approval.

Elaboration:
1. Compilation is a pure function of (current draft, accepted moves) —
   no LLM in the compile step (same posture as FR-ANA-6's deterministic
   paper generation). The LLM proposes; the compiler produces YAML.
2. The diff view shows before/after protocol YAML with per-hunk trace
   back to the design move (and its grounding) that produced it.
3. Validation runs on every compile (`protocol validate` + recipe
   `requires` pre-check, FR-ANA-2): a conversation cannot produce an
   invalid draft silently; violations bounce back into the thread as
   platform turns naming the defect.
4. Approval semantics: apply-diff (draft phase) is `researcher`+;
   protocol freeze and post-ethics amendment approval are `owner`
   (FR-PLAT-2, S3).

Fit criteria:
- F3.1 Replaying a recorded conversation's accepted moves against the
  same base draft yields a byte-identical protocol draft (determinism).
- F3.2 A move that would break schema validation is rejected at compile
  with the validation error threaded back as a conversation turn.
- F3.3 No code path applies a compiled diff without a recorded approval
  event (audit table, §FR-CONV-6).

### FR-CONV-4 (S, v2) — On-the-fly evolution, lifecycle-gated

Mid-study instrumentation and design changes SHALL be expressible in the
conversation and SHALL route through phase-aware amendment rules.

Elaboration:
1. Pre-ethics: amendments are ordinary compilations (FR-CONV-3).
2. Post-ethics-approval: a compiled amendment produces a **protocol
   version bump + amendment record** (change summary, rationale,
   grounding, approver, timestamp); consent-relevant changes (anything
   touching FR-ETH-2 scopes, content policy, or new data streams) are
   flagged `requires re-approval` and gate `data-collection` continuation
   for new sessions until an updated ethics artifact is uploaded (S3:
   the approved protocol is the executed protocol, drift is
   version-visible).
3. Instrument config evolution (probe intervals, thresholds, capture
   filters) rides the same path: the conversation proposes, the compiler
   emits the derived-config change (FR-PROT-4), and running sessions are
   never reconfigured mid-session (NFR-1 — changes apply from the next
   session).
4. Every amendment is traceable in the timeline: sessions record which
   protocol version they ran under (join keys + `protocolVersion`
   already carry this).

Fit criteria:
- F4.1 A post-approval amendment adding a new capture stream provably
  blocks new data-collection sessions until the re-approval artifact
  exists, while already-collected data remains readable.
- F4.2 A threshold tweak amendment applies to the next derived config
  and never mutates an in-flight session's settings.
- F4.3 Two sessions run under different protocol versions render
  distinguishably in the dataset and dashboard.

### FR-CONV-5 (S, v2) — The platform evolves from feedback

Researcher feedback SHALL be capturable *in the conversation* and SHALL
flow into the platform's own improvement loop.

Elaboration:
1. Any turn may be marked as platform feedback (or detected as such and
   confirmed); feedback becomes a structured **finding** (FR-META-1
   pipeline) with conversation context attached — the platform's SRS
   grows from its users' conversations exactly as the study's protocol
   grows from the researcher's (the self-application is the thesis
   point).
2. Aggregated feedback findings feed the retrospective (FR-META-2) and
   the in-platform agents (FR-META-3) to draft *inert proposals* —
   template improvements, new template candidates, UX defects — always
   human-approved, never auto-applied.
3. Cross-project learning uses **aggregates only**: no project's
   protocol content or conversation text leaves its project boundary;
   what aggregates is anonymous usage shape (which templates chosen,
   which slots most often unresolved, where conversations stall —
   `stalled-biased-confused-rca` motivates stall-point taxonomy).

Fit criteria:
- F5.1 A feedback-marked turn produces a findings row linked to the
  conversation locus; the findings dashboard card renders it.
- F5.2 The retrospective's drafted proposal cites at least the findings
  rows it used (existing FR-META-2 mechanism extended).
- F5.3 Grep-the-output: cross-project aggregation tables contain no
  conversation text, protocol content, or project-identifying strings.

### FR-CONV-6 (M, v2) — The conversation is the elicitation record

The full design conversation SHALL be stored as the study's elicitation
artifact: turns, design moves, accept/reject decisions, compilations,
approvals — exportable, and included (researcher-controlled) in the
replication kit.

Elaboration:
1. This is the provenance contribution: the trail from research idea
   to specification is *captured by construction*, not reconstructed.
   The full chain: conversation turn → design move → grounding →
   protocol hunk → instrument config → data element → recipe → claim →
   paper section.
2. Storage: append-only thread + moves + decisions tables, project-scoped
   (FR-PLAT-1), exportable as a self-contained artifact; replication-kit
   inclusion is opt-in per export (a conversation may contain
   pre-anonymization context; C3 applies).
3. Retention/redaction: deleting a study deletes its conversation;
   individual turns may be redacted with a tombstone (the move/approval
   graph stays intact — decisions are never silently unmade).

Fit criteria:
- F6.1 For a completed demo study, the export renders the full chain of
  §1 for at least one claim, navigable in both directions.
- F6.2 Replication-kit export with conversation included reproduces the
  thread + moves byte-stably; with it excluded, the kit is unchanged
  from today's format.
- F6.3 A redacted turn leaves approvals and compiled diffs intact and
  verifiable.

## 4. Interfaces (sketch — final shapes are MP-15's deliverable)

- `POST /projects/{p}/studies/{s}/conversation/turns` — append turn
  (streams the platform response; SSE).
- Design moves ride turn payloads: `{moveId, kind, target, proposal,
  grounding[], status: proposed|accepted|rejected}`.
- `POST .../conversation/compile` — compile accepted moves → draft diff.
- `POST .../conversation/approve` — apply diff (role-checked; approval
  event recorded).
- `GET .../conversation/export` — the elicitation artifact.
- LLM provider per D32 (Mistral tiers, REST, server-side tool loop);
  the design assistant's tools extend the FR-LIT-4 set with
  `search_templates`, `get_protocol_draft`, `validate_draft` — still no
  row-level participant tool (FR-ETH-4).

## 5. Degradation & failure posture

No LLM key: the conversation surface degrades to the structured designer
(FR-TPL-3 form path) with a plain-language notice — the platform remains
fully usable, just not conversational (NFR-4 external-service posture).
Provider errors mid-thread: turn marked failed, retryable; never lose
researcher input (drafts persist client- and server-side). Compilation
and validation are local and never degrade.

## 6. Paper grounding for this family

`llmrei-requirements-elicitation` (LLM elicitation interviews),
`feedaide-feedback-reports` (context-aware follow-ups),
`challenges-human-agent-communication` (the twelve communication
challenges as a design checklist for the conversation UX),
`metacognitive-demands-genai` (why unsourced suggestions must be
labeled: calibrating researcher trust),
`programmers-assistant` (conversational-assistant interaction findings),
`ironies-of-generative-ai` + `im-not-reading-all-of-that` (why review
surfaces must chunk AI output into individually decidable moves rather
than walls of prose),
`guidelines-empirical-llm-se` (the methodological floor every produced
design must meet).
