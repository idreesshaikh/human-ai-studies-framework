# Phase 24 — Import & Extensibility Tail

> Self-contained: execute this file in a fresh session at the repo root.
> Read first: `docs/VISION.md`, `docs/roadmap/README.md` (wall #7 in
> particular), `docs/roadmap/07-agent-interaction-leg.md` (the transcript
> normalizer Slice A extends), `docs/roadmap/16-curated-dataset-leg.md`
> (the `MiningAdapter` contract Slice B extends), `requirements/specs/fr-tpl.md`
> (FR-TPL-5's own note that "the contract exists the moment FR-TPL-1's
> schema is published").

**Depends on:** `agent-capture/src/agent_capture/transcript.py`
(`normalize_transcript`, the existing tolerant-parse pattern), `curated/src/curated/contract.py`
(`MiningAdapter` Protocol) + `registry.py` (`ADAPTERS` dict) + `github_adapter.py`
(the sibling this phase's importer matches) + `pseudonymize.py`/`heuristics.py`/`threats.py`
(wall #7 machinery already proven for GitHub mining), Phase 15 (template
registry, FR-TPL-1's schema), Phase 14 (role matrix — `owner`/`researcher`/
`viewer`, checked directly: no reviewer role exists yet, see Slice C).
**Satisfies:** FR-AGENT-4, FR-CUR-4, FR-TPL-5.
**Elicited:** all three already exist in `requirements/srs.md` (Could
priority) as long-deferred extension points; bundled into one phase
2026-07-21 while auditing the roadmap for requirements with no phase
owner.
**Status:** 🔶 Slice A (generic-json transcript) + Slice B (ArchiveAdapter) +
Slice C (TemplateSubmission endpoints) built; Slice C's writes to the live
registry can't be integration-tested without polluting committed files —
unit tests validate schema + routing. See the deviations log below.

## The idea

Three independent, Could-priority extension points that share a shape —
"register a second adapter behind an already-built contract" — but not a
narrative. Say so honestly rather than inventing a false unifying theme:
FR-AGENT-4 (import Copilot/generic transcripts behind the agent leg's
existing event contract) and FR-CUR-4 (import archive/replication-package
datasets behind the curated leg's existing `MiningAdapter` contract) share
wall #7 (privacy-by-construction for third-party/external content);
FR-TPL-5 (accept third-party template contributions behind the template
registry's existing schema+citation contract) does not — it is a
governance/review question, not a data-import question, and its slice
below is written that way. This phase exists so that when Phase 22's
design recommender ships ~24 archetypes, the door for someone *outside*
the owner to contribute a 25th is already built, not an afterthought.

Non-negotiable bounds, inherited verbatim:

- **Wall #7, privacy by construction — the load-bearing one for A and B.**
  Copilot/generic transcripts and mined archive datasets are *external*
  content; both get exactly the same content-free-by-default, salted-hash,
  aggregate-only treatment `agent_capture/redact.py` and
  `curated/pseudonymize.py` already prove for their respective existing
  sources. "Mined strangers get the same protection as consented
  participants" (wall #7's own clause) extends near-verbatim to an archive
  importer's subjects.
- **Wall #1.** A community template is still schema-validated + cited
  before it enters the registry (FR-TPL-1); nothing bypasses compilation.
- **No new dependency** unless a specific archive format genuinely forces
  one (NFR-10) — check the target dataset's actual file format before
  reaching for a parser library; DevGPT-style exports are typically
  JSON/CSV, both handled by the standard library already in use elsewhere
  in `curated/`.

## §0 — Traceability spine — do this first

1. **No new SRS/traceability rows needed** — FR-AGENT-4, FR-CUR-4, and
   FR-TPL-5 all already have rows in both `requirements/srs.md` (lines 62,
   207, 176) and `requirements/traceability.md` §1 (lines confirmed
   present), all currently ⬜. This phase's verification flips them to ✅
   per slice as each lands (golden rule 3) — do not renumber any of the
   three.
2. **Glossary:** no new terms anticipated for A/B (they reuse "transcript,"
   "adapter," "cassette" as already used in `agent-capture`/`curated`
   docs). Slice C likely needs one: *Template submission* / *Template
   review* — add if the reviewer workflow (below) introduces a named
   state a researcher-facing surface needs to reference.
3. **Tracker row:** this phase already has its own "Import & extensibility
   tail (24)" heading + row in `docs/roadmap/README.md` (added alongside
   this spec) — flip its status only once verification passes. Since the
   three slices are independent, consider flipping FR-AGENT-4/FR-CUR-4
   before FR-TPL-5 if they land first — partial tracker status (`🔶` with
   which sub-item is pending named) is honest and expected here, not a
   defect (mirrors how Phase 14/15/16/18 already carry `🔶` for exactly
   this reason).

**Build-vs-adopt:** no new adoption row needed unless a parser dependency
proves necessary for the specific archive format chosen for Slice B (check
first; log a `build-vs-adopt.md` row only if one is genuinely required).

## Slices

### Slice A — Generic / Copilot transcript adapter (FR-AGENT-4)

Python only, `agent-capture/`.

1. Extend `agent_capture/transcript.py`'s tolerant-parse pattern
   (`normalize_transcript` already handles Claude Code's JSONL shape
   tolerantly — missing fields degrade gracefully rather than raising) to
   a second input format. Concretely: a `format` parameter or a
   format-sniffing dispatch (`normalize_transcript(path, format="claude-code"
   | "copilot-chat" | "generic-json")`), each format's parser producing the
   *same* `study_event`/`seq` output contract — no new event shape, no
   `SCHEMA_VERSION` bump (this is a second input, not a new output).
2. **Content policy still applies.** Whatever content-policy gate
   `redact.py` enforces for Claude Code transcripts (metadata-only /
   redacted / full, per the protocol's `agentCapture.contentPolicy`)
   applies identically regardless of source format — the adapter boundary
   is purely "which raw export format am I parsing," never a second
   privacy path.
3. **Tests:** a Copilot Chat export fixture (or generic JSON fixture if no
   real Copilot export is available to test against — check first,
   fabricate a minimal synthetic one otherwise and say so in the
   deviations log) round-trips through `normalize_transcript` into the
   same `study_event` shape Claude Code transcripts produce; the content
   policy gate applies identically across formats (a table-driven test
   parametrized over format × policy).

### Slice B — Archive / replication-package importer (FR-CUR-4)

Python only, `curated/`.

1. A new `ArchiveAdapter` in `curated/src/curated/archive_adapter.py`
   implementing the existing `MiningAdapter` Protocol
   (`curated/src/curated/contract.py`), registered in `registry.py`'s
   `ADAPTERS` dict alongside `GitHubAdapter.source: GitHubAdapter` — no
   change to the job runner or any downstream consumer, which already
   dispatches on `source` name (confirmed: `registry.get_adapter(source,
   ...)` is the only call site that needs to know a new source exists).
2. Reuse `pseudonymize.py` and the validity-threats record (`threats.py`)
   verbatim — an archive's authors are exactly the "mined strangers" wall
   #7 already governs for GitHub mining; do not build a second
   anonymization path.
3. **Tests:** a cassette-recorded fixture (matching `curated/`'s existing
   `cassettes/` + `cassette.py` convention — offline, zero network, same
   as `GitHubAdapter`'s own test setup) proves the archive importer
   produces rows in the same join-keyed schema `GitHubAdapter` does, and
   that pseudonymization/threats-record coverage is identical.

### Slice C — Third-party template contribution + review gate (FR-TPL-5)

Middleware + platform. **No privacy dimension** — say so explicitly rather
than stretching wall #7 to cover this slice.

1. A `TemplateSubmission` model (middleware `db.py`, mirrors
   `EnrollmentToken`'s mint/list/revoke shape but for a different lifecycle:
   `submitted → under-review → accepted | rejected`) — schema-validated
   against FR-TPL-1's existing template schema and requiring a citation
   (FR-CONV-2's grounding contract, reused: a template with no source
   paper is rejected at validation, not just discouraged).
2. **Role gap, confirmed by reading `capabilities.ts` directly:** the
   current role matrix is `owner`/`researcher`/`viewer` only — no
   reviewer/approver role exists. Decide explicitly (don't default
   silently): either (a) `owner` doubles as reviewer for now — no new
   role, simplest, matches this platform's single-facilitator-mode
   default (`auth.py`'s `none`/`token` modes only ever resolve one
   identity anyway); or (b) add a fourth role. **Recommendation: (a)** —
   a fourth role is a Platform-shell-level change (Phase 14 territory)
   disproportionate to a Could-priority extension point; template review
   gated on `owner` capability is sufficient until multi-reviewer
   workflows are actually requested.
3. Endpoints: `POST /templates/submissions` (any authenticated
   researcher+), `GET /templates/submissions` (owner), `POST
   /templates/submissions/{id}/decision` (owner; accepted → registers into
   the template registry via the existing `template_registry.py` path,
   same as an owner-authored template; rejected → recorded with a
   plain-language reason, never silently dropped).
4. **Tests:** a submission failing schema validation or missing a citation
   is rejected at submission time, not after review; an accepted
   submission becomes indistinguishable from an owner-authored template to
   every downstream consumer (the design recommender, the conversational
   designer) — no second-class template type.

## Degrees of freedom

- **Slice A's format-dispatch mechanism** — an explicit parameter vs.
  content-sniffing; either, as long as an unrecognized format fails with a
  plain message rather than silently mis-parsing.
- **Slice B's target archive** — DevGPT (arXiv:2309.03914) is the
  SRS-cited example, not a hard requirement; any published,
  citable dataset with a stable schema is an acceptable first target.
- **Slice C's submission UI** — a form vs. a YAML-paste surface; either,
  within NFR-12's registers. A CLI-only submission path (no UI at all,
  just the endpoints) is also acceptable for this Could-priority item's
  first cut — log it as a deviation if chosen, not silently.

## Acceptance (maps to fit criteria)

- FR-AGENT-4: a Copilot/generic transcript import produces the same
  `study_event` shape and respects the same content-policy gate as the
  existing Claude Code path — a downstream recipe/report cannot tell which
  adapter produced a row.
- FR-CUR-4: an archive import produces rows in the one join-keyed schema,
  pseudonymized and threats-recorded identically to GitHub mining; the job
  runner dispatches to it purely by `source` name, no special-casing.
- FR-TPL-5: a schema-invalid or uncited submission is rejected before
  reaching review; an accepted submission is a first-class template
  indistinguishable from an owner-authored one.
- Wall #7: grep-the-output tests for both A and B confirm no raw
  transcript/archive content beyond the existing content-policy/
  pseudonymization bounds ever persists.

## Verification steps

1. `uv run pytest && uv run ruff check .` — includes Slice A's
   multi-format transcript tests, Slice B's archive-adapter cassette
   tests, and Slice C's submission-validation tests.
2. `platform/`: `npm run check` green if Slice C ships a UI; skip this gate
   entirely (and say so in the deviations log) if Slice C ships
   CLI/endpoint-only per its degree of freedom above.
3. Manual check: register the archive adapter in `registry.py` and confirm
   `curated`'s existing CLI (`curated mine --source archive ...` or
   equivalent, matching the GitHub adapter's own invocation pattern) runs
   it end to end against the cassette fixture.
4. Confirm FR-AGENT-4/FR-CUR-4/FR-TPL-5's traceability rows and this
   phase's tracker row are flipped only after 1–3 are green for the
   corresponding slice (golden rule 3; partial flips are honest here).

## Deviations log

Record departures here and in `requirements/traceability.md` §3 as they
occur — in particular: which archive dataset was actually targeted for
Slice B, whether Slice C shipped a UI or CLI-only, and the role-gap
decision (a vs. b above) actually taken.
