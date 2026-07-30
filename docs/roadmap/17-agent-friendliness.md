# Phase 17: Agent-Friendliness

> **Note (2026-07-18):** Phase 17 is built. The FR-PROT-9 fit fixture was
> originally the `context-ablation-2026.yaml` demonstrator draft; that draft
> (and the comprehension-debt draft) were pilot trial studies, since removed
> as clutter (see the traceability phase-completion log). The fixture now
> lives at `protocol/tests/fixtures/agent-participant-v3.yaml`, a neutral,
> purpose-built v3 protocol. Mentions of `context-ablation-2026.yaml` below
> are the historical build account; the current fixture is the tests' file.

> Self-contained: execute this file in a fresh session at the repo root.
> Read first: `docs/VISION.md`, `requirements/specs/fr-agf.md` (the
> requirement of record), `requirements/srs.md` FR-PROT-9 row,
> `protocol/tests/fixtures/agent-participant-v3.yaml` (the fixture this phase
> makes valid), `docs/design/architecture.md` (manifest placement), and
> `docs/roadmap/README.md` (walls + charter). For Claude Code hook and
> transcript formats, verify against current docs via the
> `claude-code-guide` agent, never memory.

**Depends on:** Phase 14 (the shell: the manifest describes a platform
with projects and auth; the UI carries the attribute convention), Phase 15
(templates + corpus endpoints the manifest indexes), Phase 12 (agent leg +
task harness, FR-PROT-9's instruments). **Satisfies:** FR-AGF-1..3,
FR-PROT-9. **Elicited:** owner, Phase 01 rev 8 ("a lot of metadata that
agents when run can understand") + rev 11 (agent participants).
**Status:** Built (2026-07-18): all four slices implemented and tested;
the manifest + AGENTS.md + schema vNext + `data-agent` annotations are
green, with CI drift gates and the scripted agent-discovery proof
(in-process and against a live boot).

## The idea

Two kinds of AI agents meet this platform: agents that **operate** it (a
researcher's Claude Code driving the API; browser agents driving the UI)
and agents that are **studied by** it (FR-PROT-9: the participant *is*
an agent configuration under the task harness). This phase serves both
with one principle: **everything an agent needs is generated from the
documents of record, never hand-maintained**: context that drifts is
worse than no context (`evaluating-agents-md`; `agents-md-efficiency`).
After this phase, an agent given nothing but a deployment URL can
discover the API, validate a protocol draft against the real schema, and
speak the platform's vocabulary, and the platform can run a study whose
participants are agents.

Non-negotiable bounds:

- **No hand-written manifest content** (FR-AGF F1.1): every value is
  traceable to a generated source; a grep finds no literal capability
  strings outside the generator.
- **Generated context goes stale loudly** (F2.2): CI fails on drift,
  exactly like a lockfile.
- **Consumers branch on version** (FR-PROT-2): agent-participant support
  is a bumped `protocolVersion`, and v1 protocols stay valid under v1
  rules forever.
- **The FR-ETH-4 boundary is unchanged**: the manifest and vocabulary
  endpoints expose *structure* (schemas, capabilities, glossary), never
  data. Nothing in this phase widens what any agent can read.

## Slices

### Slice A: The platform manifest (FR-AGF-1)

1. `GET /.well-known/platform-manifest`: unauthenticated, assembled at
   startup in `middleware/src/middleware/manifest.py` from:
   FastAPI's own `openapi()` (the API surface), the published JSON
   Schemas (event, protocol, template, with versions), the
   requirements/glossary parser (FR-DASH-9, already live), the template
   registry index, the corpus index count, and the deployment's auth
   mode. Shape per `fr-agf.md` §2; extend fields freely (see freedoms)
   but every value generated.
2. **The scripted proof** (F1.2): a committed script
   (`scripts/agent_manifest_demo.py` or a documented Claude Code
   session recipe, builder's choice) that, given only the manifest URL:
   discovers the API via the linked OpenAPI doc, fetches the protocol
   schema and validates a draft against it, and answers "what does
   `condition` mean here?" from the vocabulary endpoints, zero
   repository access. This script is the fit criterion made executable
   and doubles as living documentation.

### Slice B: Generated context files (FR-AGF-2)

1. `scripts/generate_agents_md.py` → `AGENTS.md` at the repo root (and
   shipped in deployments), generated from: the glossary, the SRS index
   (IDs + one-liners), a manifest snapshot, and the **System invariants**
   section of CLAUDE.md (parsed by heading, CLAUDE.md itself stays
   hand-written: it is the generator's *input* for invariants; judgment
   stays human, facts get generated).
2. **CI drift check**: regenerate + `git diff --exit-code AGENTS.md`
   in the existing CI workflow. Editing the glossary without
   regenerating turns CI red (F2.1/F2.2), same posture as lockfiles.
3. Generation is deterministic (stable ordering, no timestamps in
   content) so the diff check is meaningful.

### Slice C: Agent participants (FR-PROT-9)

The protocol schema learns that a participant can be an agent:

1. Schema vNext (bumped `protocolVersion`): participant entries may be
   **anonymized agent-configuration IDs** recording tool + model;
   `tern` becomes optional for agent participants; the agent
   leg + task harness (Phase 12) are the primary instruments. Validators
   branch on version: the v1 validator's behavior is untouched.
2. **The fit fixture is the spec**: `context-ablation-2026.yaml`
   (deliberately failing v1 validation today) must validate **unmodified
   except the version bump** (the SRS row's criterion). If it can't,
   the schema design is wrong, not the fixture.
3. Downstream sanity, not full support: `protocol derive` produces
   harness-oriented config for agent participants; the analysis plan
   validates (recipes may still be pending: loud FR-ANA-2 failure is
   the correct state, as with the comprehension-debt draft).
4. Glossary terms already exist (rev 11: Agent participant, etc.);
   code and schema field names follow them.

### Slice D: Semantic UI annotations (FR-AGF-3, the convention)

1. Stable `data-agent` attributes on navigational landmarks and
   decision-bearing components (`data-agent="move-card"`,
   `"draft-rail"`, `"project-switcher"`, `"compile-button"` …): the
   `data-tour` discipline generalized. Retrofit the Phase 14/15 components
   (small, mechanical); new components adopt it from birth.
2. One conventions file (`platform/docs/agent-annotations.md`): naming
   rules, stability promise (renaming an attribute is a breaking change
   logged like one), and the current inventory: generated or checked
   by lint if cheap, hand-listed if not (builder's call; drift here is
   low-stakes until a browser-agent consumer exists, which is why
   FR-AGF-3 is a C).

## Degrees of freedom

- **Manifest field extensions**: the §2 shape is the floor; add
  generated fields agents plausibly want (rate limits, deployment
  flavor, demo pointers). Never a hand-written value.
- **Demo harness**: Python script vs. documented Claude Code recipe
  vs. both, for the F1.2 proof.
- **Where generation hooks**: pre-commit, CI-only, or a `make` target;
  the binding requirement is only that CI catches drift.
- **Schema-vNext mechanics**: whether agent participants are a
  participant-entry variant or a parallel section is yours; the fixture
  validating unmodified (± version) is the non-negotiable test of the
  choice.
- **Attribute inventory**: which components carry `data-agent` beyond
  landmarks and decision points; err toward fewer, stabler names.

## Acceptance (maps to fit criteria)

- FR-AGF-1: F1.1 grep finds no literal capability strings outside the
  generator; F1.2 the scripted demo runs green against a fresh boot.
- FR-AGF-2: F2.1 glossary edit + rebuild provably updates AGENTS.md;
  F2.2 CI red on drift.
- FR-AGF-3: annotations present on the named surfaces; conventions doc
  exists; renames are logged.
- FR-PROT-9: `context-ablation-2026.yaml` validates under vNext
  unmodified except the version bump; v1 protocols still validate under
  v1 rules (regression suite).

## Verification steps

1. `uv run pytest && uv run ruff check .`: manifest generator,
   AGENTS.md generator (golden-file test), schema-vNext validator
   branch, fixture validation.
2. The F1.2 agent demo, run against a real local boot, output captured.
3. CI run demonstrating the drift check firing (one deliberate stale
   commit on a branch, then fixed).
4. `npm run build && npm run lint` in `platform/` after the annotation
   retrofit.

## Deviations log

Record departures here and in `requirements/traceability.md` §3.

**2026-07-18: built.** What landed:

- **Slice A (manifest, FR-AGF-1):** `manifest.py` already existed but had
  real bugs. Fixed: it now reports the deployment's *resolved* auth mode
  (was reading a never-set `AUTH_MODE` env), reads the protocol-version
  *enum* (was returning `[1]` via a stale `const` lookup), caches per
  `(deployment, auth_mode)` (was a single global that leaked auth mode
  across deployments), and offers a deterministic snapshot form (no
  timestamp) for AGENTS.md. Fixing it surfaced **two latent bugs from the
  parallel build**: (1) the `/schemas/*`, `/templates`, `/papers/index`
  endpoints resolved their paths with one too few `.parent` calls, so they
  served hardcoded fallbacks / empty; an agent following the manifest got
  a stub schema; (2) the manifest route itself 422'd on every request
  because `Request` was imported *inside* the route factory under
  `from __future__ import annotations`, so FastAPI couldn't resolve the
  annotation. Both fixed and regression-tested. Added
  `scripts/agent_manifest_demo.py` (the F1.2 proof), green in-process and
  against a live `python -m middleware` boot.
- **Slice B (AGENTS.md, FR-AGF-2):** `scripts/generate_agents_md.py`
  generates `AGENTS.md` deterministically from the glossary, the SRS index,
  a manifest snapshot, and CLAUDE.md's System-invariants section (CLAUDE.md
  stays the hand-written *input*). `--check` is the drift gate; wired into
  `ci.yml` plus a pytest that fails on drift.
- **Slice C (agent participants, FR-PROT-9):** schema vNext bumps
  `protocolVersion` to accept `3` and makes `tern` conditional
  (required at v1/v2; at v3 the study needs ≥1 of overlay / agentCapture /
  taskHarness), plus an optional `participants.agents` list (tool+model).
  `context-ablation-2026.yaml` validates under v3 with **only** the version
  bump (the fit criterion), while v1/v2 behavior is untouched (regression
  suite). `derive` gained an agent branch: `overlay-settings` fails cleanly
  on an agent study and `agent-hooks` produces the harness config.
- **Slice D (annotations, FR-AGF-3):** 13 stable `data-agent` names on the
  Phase 14/15 landmarks and decision points, `platform/docs/agent-annotations.md`
  (naming rules, the stability-is-a-contract promise, the inventory), and
  `check-agent-annotations.mjs` keeping the doc and code in sync (in
  `npm run check`).

Deviation: the agent-participant analysis recipe `cost-effectiveness-frontier`
named in the fixture is still unbuilt, so `analysis validate` fails loudly on
it: the correct state (FR-ANA-2), matching the comprehension-debt draft.
