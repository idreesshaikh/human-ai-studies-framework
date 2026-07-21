# Phase 19 — The Live Capture Link (study conductor, part 1 of 3)

> Self-contained: execute this file in a fresh session at the repo root.
> Read first: `docs/VISION.md`, `docs/roadmap/README.md` (the walls + the
> autonomy charter — both bind this phase; **wall #6 in particular, upheld
> as a hard wall**), `requirements/specs/fr-plat.md` (the role matrix +
> invitation pattern this reuses), `requirements/specs/fr-conv.md`
> (amendments — how `instruments` change between sessions),
> `requirements/metric-coverage.md` (what the metrics *are*, cited),
> `extension/PROJECT_GUIDE.md` (the core/adapter split this must not break),
> `docs/design/architecture.md`, `docs/design/data-model.md`,
> `docs/design/sequences.md`.

**Depends on:** Phase 03 (ingestion middleware, the `/ingest/*` contract),
Phases 05–06 (the TERN extension — cognitive + behavioral
legs, the `HttpSink`, the per-signal capture flags), Phase 14 (projects,
roles, the `authz` choke point, the `Invitation` mint/accept pattern, the
study workspace tabs), Phase 18 / FR-CONV-4/5 (the amendment engine — how a
study's `instruments` change *between* sessions, always at a session
boundary), Phase 13 / FR-ETH-1 (the ethics gate that guards data
collection).
**Satisfies:** FR-INST-20 (enrollment via one pairing token), FR-ING-7
(mint/verify tokens; authenticated-but-non-blocking ingest), FR-INST-21
(HTTP capture-config delivery, applied only at session boundaries behind a
pre-flight), FR-DASH-10 (the enrollment surface). **Upholds wall #6 as a
hard wall** — a running session is never reconfigured.
**Elicited:** owner, 2026-07-19 — *"this is not just a study designer but a
study conductor… connect the extension in VS Code to the dashboard, a
session token provided, capturing only the metrics the researcher wants,
out-of-the-box… make sure it fits the platform, not a side feature
lurking."*
**Status:** Specced (2026-07-19). Not built.

## The idea

Today the platform *designs* a study to the last cited detail — and then
stops at the water's edge. To actually *run* it, a participant hand-types
a `participantId`, hand-picks a `condition`, and hand-pastes an HTTP
endpoint into VS Code settings; nothing checks that those match a real
study, and the researcher's carefully-compiled `instruments` block reaches
the IDE only through a manual CLI step. That gap is why the product reads
as a designer, not a conductor.

This phase closes it. **The protocol you talked into existence becomes the
thing the IDE runs.** A researcher mints a **pairing token** from the
study; the participant pastes **one connection string** into their editor;
the extension redeems it, receives its identity, its ingest endpoint, and
the study's **capture config** derived from the same protocol YAML,
displays the protocol's own consent statement, and begins streaming
join-keyed events onto the one timeline. No hand-typed IDs. No stray
endpoints. No config drift. One document of record, all the way to the
participant's cursor.

This is **part 1 of the study-conductor arc**: Phase 19 builds the *link*
(pairing + the config channel + a minimal enrollment surface); Phase 20
("the capture console") builds the grounded per-metric toggle UI on the
channel this phase opens; Phase 21 ("the conductor overlay") enriches the
in-editor participant experience. Part 1 is the load-bearing rung — the
other two are unbuildable without it, and it is the missing step in the
platform loop (VISION § "the adopting researcher's journey": *…gates,
ethics, **data (live sessions)** …*).

Non-negotiable bounds, inherited verbatim:

- **The protocol is the sole document of record** (wall #1). The capture
  config is *derived* from `instruments.*` (FR-PROT-4 `derive`), never
  authored beside it. Remove the link and the CLI derive still produces
  identical settings.
- **Join keys everywhere, and now server-authoritative** (wall #4). A
  credentialed row's `participantId`/`condition` are stamped by the
  middleware from the credential, not trusted from the client.
- **Ingest never blocks and never drops; running sessions are never
  reconfigured** (wall #6, hard). Adding a credential must not turn a
  momentary auth hiccup into lost data: un-credentialed/mismatched rows are
  stored and flagged (FR-ING-6), never rejected. Capture config is applied
  only at a session *boundary*, never mid-run; the "forgot a toggle" case is
  caught by the pre-flight before the clock arms (§Slice B / FR-INST-21).
- **Privacy by construction** (wall #7). The token and the session
  credential are transport secrets — they MUST NOT appear in any stored
  event, export, or log line. Grep-the-output is a test, not a hope.
- **`src/core` never imports `vscode`** (NFR-3, `PROJECT_GUIDE.md`). The
  pairing *transport* lives in the adapter; the connection-string parse,
  the consent-gate state machine, the pre-flight summary, and the
  config-apply logic live in `src/core`, unit-tested with injected clocks.
- **Everything degrades** (wall #9). No middleware reachable → the
  extension falls back to its existing local-settings path and the JSONL
  source-of-truth file; pairing is convenience over a working base, never
  a new hard dependency. No new runtime dependency is adopted
  (§ Requirements) — `secrets`, SQLAlchemy, and VS Code built-ins only.

## §0 — Traceability spine — do this first

The execution model puts the traceability spine first. Before any code:

1. **Add the four requirement rows** to `requirements/srs.md` (FR-INST-20,
   FR-ING-7, FR-INST-21, FR-DASH-10 — text in § Requirements) and their
   `requirements/traceability.md` §1 rows (status ⬜ until verified).

2. **Add the glossary terms** (`requirements/glossary.md`): *Pairing
   token*, *Connection string*, *Session credential*, *Capture config*,
   *Enrollment* (definitions in § Requirements). Ban "session token" as a
   bare synonym — the minted artifact is a *pairing token* (with a `grain`);
   the exchanged bearer is a *session credential*.

3. **Add the tracker row**: this phase in `docs/roadmap/README.md` under a
   new "Study conductor (19–21)" heading, status specced.

**Wall #6 stands unchanged, and this phase upholds it:** a running session
is never reconfigured. The "don't waste a session on a forgotten toggle"
requirement is met at the session *boundary* — the capture pre-flight
(before the clock arms) plus a cheap abort+restart of a mis-instrumented
session — not by mid-run mutation (§Slice B, FR-INST-21). No decision-ledger
entry is needed (nothing is amended) and no `build-vs-adopt` adoption row is
needed (nothing new is adopted).

## Slices

### Slice A — Backend: tokens, the config channel, authenticated ingest

Middleware only; the extension and existing ingest keep working throughout.

1. **Model** `EnrollmentToken` (`middleware/src/middleware/db.py`, mirrors
   `Invitation`):

   ```
   enrollment_token(
     id TEXT PK, study_id REFS study, participant_id TEXT, condition TEXT,
     grain TEXT CHECK(grain IN ('participant','session')),
     token TEXT UNIQUE, credential TEXT NULL,      -- credential minted on redeem
     expires_at TEXT, revoked_at TEXT NULL, redeemed_at TEXT NULL,
     created_by TEXT, created_at TEXT)
   ```

   `condition` is validated against the protocol's `conditions`;
   `participant_id` against the `P<n>` convention within
   `participants.planned` (reuse `_ProtocolCheck`). The credential is an
   opaque `secrets.token_urlsafe(32)` stored on the row — no new crypto
   dependency, no JWT.

2. **Mint / list / revoke** (role-gated through the `authz` choke point; add
   a `mint_token` capability to the `CAPABILITIES` dict — researcher+):
   - `POST /studies/{id}/enrollment/tokens` — body `{count, grain}` mints a
     **batch** (P1…Pn, conditions assigned by the protocol's
     counterbalancing) or a single token; returns `[{participantId,
     condition, connectionString, url}]`. **Refuses (409)** unless the
     study has cleared the ethics gate (FR-ETH-1) — no collecting before
     approval.
   - `GET /studies/{id}/enrollment/tokens` — list with derived status
     (`unredeemed` | `paired` | `streaming`, the last from the live
     session-status feed).
   - `DELETE /enrollment/tokens/{id}` — revoke (sets `revoked_at`; a
     revoked token's credential stops verifying).

3. **Redeem** `POST /pair/redeem` — body `{token}` (unauthenticated: the
   token *is* the credential-to-be). Validates live/unexpired/unrevoked and,
   for `grain: session`, unredeemed. Returns:

   ```jsonc
   { "participantId": "P07", "condition": "ai-assisted",
     "sessionCredential": "<opaque>", "ingestEndpoint": "…/ingest/events",
     "captureConfig": { "captureConfigVersion": 3, "tern": {…} },
     "consentStatement": "<verbatim from protocol>",
     "contentPolicy": "metadata-only" }
   ```

   For `grain: session` the token is marked `redeemed_at`; for `participant`
   it stays reusable. Idempotency: a re-redeem of a `session` token returns
   410 with a plain-language body.

4. **Capture-config endpoint** `GET /studies/{id}/capture-config` — the
   derived, versioned config, produced by lifting `derive_overlay_settings`
   (today CLI-only, `protocol/src/protocol/derive.py`) behind HTTP, sliced
   per `producer` query param (`overlay` → the extension's flat
   `tern.*` flags; `agent` → content policy; extensible). Carries
   `captureConfigVersion` (bump on any `instruments.*` change, wall #5).

5. **Authenticated-but-non-blocking ingest.** `POST /ingest/events` and
   `/ingest/metrics` accept an optional `Authorization: Bearer
   <sessionCredential>`. When present and valid: **server-stamp**
   `participant_id`/`condition` from the token (override client values) and
   record `authenticated: true`. When absent: unchanged legacy behaviour
   (fire-and-forget, client-supplied keys). When present but
   invalid/expired/revoked, **or** present and valid but the client-supplied
   keys disagree: **store and flag** (`unauthenticated` / `credential-
   mismatch`) — never 401, never drop (FR-ING-6, wall #6). The `auth.py`
   docstring ("ingest is never authenticated in any mode") is updated to
   describe this non-blocking, override-on-match, flag-on-mismatch contract.

6. **Tests** (`middleware/tests/`): mint refuses before the ethics gate;
   batch minting assigns counterbalanced conditions; redeem returns the
   derived config + verbatim consent; `session`-grain single-use (second
   redeem 410); server-stamp overrides a spoofed `participantId`;
   mismatch/expired/absent-credential rows all land stored-and-flagged, none
   dropped, none 401; grep-the-stored-rows asserts no token/credential
   string ever persists into an event payload or export.

### Slice B — Extension: the one-paste connect experience

Adapter + core, honoring the split. **Bumps no `SCHEMA_VERSION`** — event
shape is unchanged; this is transport + config source + a consent gate.

1. **Core** (`src/core`, `vscode`-free, injected clock, unit-tested):
   - `connectionString.ts` — parse/format `{ serverUrl, token }` (a compact,
     copy-safe encoding; reject malformed input with a typed error).
   - `pairing.ts` — a pure state machine: `idle → redeeming → consent-pending
     → paired → capturing`, plus `unpaired-fallback`. Owns nothing
     `vscode`; the adapter feeds it transport results and renders its state.
   - `captureConfig.ts` — apply a `captureConfig` onto the effective
     capture flags **at a session boundary only**; a `captureConfigVersion`
     comparison decides whether a re-pull is due at the next session start.
     No mid-session mutation, no diff-classification logic.
   - `preflight.ts` — build the "will capture / will not capture" summary
     from the effective config for display before the clock starts.
   - `consentGate.ts` — the acknowledgment state: no event leaves the
     machine until the participant accepts the shown consent statement +
     content policy (FR-AGENT-5 verbatim).

2. **Adapter** (`src/vscode`):
   - Command **`tern.connectToStudy`** — a single input box
     ("Paste the connection string from your study invite"), calls
     `/pair/redeem`, drives the `pairing` machine, persists the credential
     to `SecretStorage` (never settings/JSON), writes the resolved
     `participantId`/`condition`/`endpoint` into the session (not
     hand-typed), and applies the config.
   - `HttpSink` gains an `Authorization: Bearer` header from `SecretStorage`
     (still fire-and-forget; a 401 is impossible by design — see Slice A —
     so nothing new can block the session).
   - **Consent surface** — the existing glassmorphic webview pattern
     (`endSurvey.ts`) reused to present the consent statement + content
     policy with an explicit "I consent" gate before capture starts.
   - **Capture pre-flight** — before `session.start()` arms the clock, show
     the pre-flight summary (a compact, dismissible panel); the researcher
     sees the same pending config on the dashboard (Slice C) and can fix a
     forgotten toggle while the participant is still on the pre-flight — the
     change lands because config is re-pulled at session start, *before* the
     clock. Once a session is running its config is frozen (wall #6); a
     session found mis-instrumented is aborted and restarted (the pausable,
     crash-recoverable clock, FR-INST-3) — seconds lost, not a session.
   - **Getting-Started walkthrough** (`contributes.walkthroughs`, built-in):
     "Connect to your study" → paste → consent → begin. The legacy manual
     participantId/condition/endpoint settings remain as the offline
     fallback, demoted from the default path.

3. **Tests** (`extension/test/`, mocked timers): connection-string
   round-trip + malformed rejection; the pairing state machine transitions;
   config-apply flips exactly the intended flags; the consent gate blocks
   emission until acknowledged; the pre-flight summary reflects the applied
   config; a config change arriving while a session runs does **not** mutate
   the running session (applied only at the next session start); fallback
   path unchanged when no credential is present.

### Slice C — Dashboard: the enrollment surface (FR-DASH-10)

A new tab/panel in the study workspace (`platform/`, alongside
Conversation/Library/Data/Lifecycle), **not** a separate screen — it reads
as part of the study, because it is.

- **`EnrollmentPanel`** — mint control (count + grain picker), a table of
  participants with **copy-link** as the primary affordance (reuse
  `InviteDialog`'s pattern), status chips (`unredeemed` / `paired` /
  `streaming`, live from the session-status feed FR-DASH-3), and revoke.
- Role-gated via the existing `capabilities.ts` mirror of the matrix
  (`mint_token`); viewers see status, not controls.
- **Pre-flight visibility**: each `paired`/awaiting row shows the capture
  config that IDE will run under, so a researcher catches a forgotten toggle
  before "begin".
- NFR-12: token-only styling, both themes + reduced-motion, axe clean,
  keyboard-complete mint→copy→revoke. Empty state teaches ("Mint a link for
  each participant; they paste it once and their editor joins the study").

### Slice D — Session-boundary refresh + the deep link

Enhancements on Slice B, same redeem path — no second mechanism, no live
control channel (wall #6).

1. **Session-boundary re-pull.** The extension keeps the
   `captureConfigVersion` of the config it last applied. At **each session
   start** (not mid-run) it calls `/capture-config`; if the version differs,
   it applies the new config behind the pre-flight before arming the clock.
   That is the *only* point at which capture changes take effect — a toggle a
   researcher flips while a session is open lands on the participant's *next*
   session, never the current one.
2. **Deep link** (`vscode://…/pair?c=<connectionString>`) via
   `registerUriHandler`, wired to the same `/pair/redeem` flow; the
   dashboard's copy-link gains an "Open in VS Code" companion so a
   participant who already has the extension skips the paste entirely.

## API surface (additions)

```
POST   /studies/{id}/enrollment/tokens     mint batch|single (researcher; ethics-gated) → [{participantId,condition,connectionString,url}]
GET    /studies/{id}/enrollment/tokens      list + live status (researcher/viewer)
DELETE /enrollment/tokens/{id}              revoke (researcher)
POST   /pair/redeem                         exchange token → {identity, sessionCredential, captureConfig, consent} (public; token-guarded)
GET    /studies/{id}/capture-config?producer=overlay   derived, versioned capture config
# /ingest/events and /ingest/metrics gain optional Bearer auth (server-stamp on match, flag on mismatch, never 401)
```

## Requirements (added to `srs.md` + `traceability.md` in §0)

- **FR-INST-20 (M)** — The framework SHALL let a participant's IDE **enroll**
  into a study by redeeming one **pairing token** (delivered as a
  **connection string** encoding middleware URL + token) that resolves its
  identity (`participantId`, `condition`), ingest endpoint, and capture
  config with no hand-entered IDs or endpoint. Tokens are minted
  per-participant (reusable) or per-session (single-use), grain chosen at
  mint. *Traces to:* the platform loop's live-data rung; S6/S7 adoption;
  RQ-P1–P5.
- **FR-ING-7 (M)** — The middleware SHALL mint, list, and revoke pairing
  tokens (study-scoped, ethics-gated, role-gated) and verify them on
  redemption, issuing a short-lived **session credential**. Credentialed
  ingest SHALL server-stamp `participantId`/`condition` from the credential;
  un-credentialed or mismatched rows SHALL be stored and flagged, never
  rejected and never blocking. *Traces to:* RQ-F1; S3; NFR-1/2; FR-ING-6.
- **FR-INST-21 (M)** — The middleware SHALL serve a **capture config**
  derived deterministically from the protocol's `instruments` block; the IDE
  SHALL apply it at pair and at **each session start** behind a **capture
  pre-flight** that states what will and will not be captured before the
  session clock arms. A **running session SHALL NOT be reconfigured**
  (wall #6): a config change made while a session is open takes effect only
  at that participant's next session start, and a session found
  mis-instrumented is aborted and restarted (FR-INST-3). Config carries a
  `captureConfigVersion` consumers branch on (wall #5). *Traces to:* wall #6;
  FR-PROT-1/2/4; FR-INST-3; RQ-P*.
- **FR-DASH-10 (S)** — The platform SHALL provide an **enrollment surface**
  in the study workspace: mint pairing tokens (batch/single, pick grain) as
  copy-links with live status (unredeemed/paired/streaming) and revoke,
  role-gated. *Traces to:* S1; FR-DASH-3; the platform loop.

**Glossary additions:** *Pairing token* (the minted artifact binding a study
+ participant + condition, with a `grain`); *Connection string* (the
copy-safe encoding of middleware URL + pairing token the participant
pastes); *Session credential* (the short-lived bearer exchanged for a token,
which authenticates ingest); *Capture config* (the versioned, protocol-
derived set of enabled instruments/metrics an IDE applies at a session
boundary); *Enrollment* (a participant's IDE joining a study by redeeming a
pairing token). Ban bare "session token".

**Build-vs-adopt:** no adoption. `secrets`, SQLAlchemy, VS Code built-ins,
existing `fetch`/`HttpSink` only (NFR-10 satisfied by using what's here).

## Degrees of freedom

- **Connection-string encoding** — any compact, copy-safe, tamper-evident
  form (base64url of a small JSON, or `url#token`); yours, as long as a
  malformed paste fails with a plain message.
- **Enrollment panel layout** — its own tab vs a section of Lifecycle;
  either, within the registers of NFR-12.
- **Pre-flight presentation** — panel, notification, or status-bar
  expansion; must state capture on/off clearly before the clock and be
  dismissible without stealing focus.
- **Batch minting UX** — inline table vs generated CSV of links; pick what
  a researcher running 20 participants would actually want.
- **`captureConfigVersion` scheme** — monotonic int or content hash; must
  change iff the derived config changes.

## Acceptance (maps to fit criteria)

- FR-INST-20: a fresh VS Code + a pasted connection string reaches
  "capturing" with zero hand-typed IDs/endpoint; the recorded events carry
  the token's `participantId`/`condition`.
- FR-ING-7: minting before the ethics gate is refused; a spoofed
  `participantId` on a credentialed row is overwritten server-side; an
  expired/absent credential still lands the row (flagged), never 401; no
  token/credential appears in any stored row or export (grep test).
- FR-INST-21: the config the IDE applies is byte-equal to `protocol derive
  overlay-settings`; a forgotten toggle enabled before "begin" takes effect
  at the pre-flight; a change made while a session runs does not alter that
  session and is applied only at the next session start.
- FR-DASH-10: mint→copy→pair→streaming status visible; revoke stops a
  `session`-grain re-pair; viewer sees no controls.
- Wall #6: a test proves an `instruments.*` change during an open session
  leaves that session's applied config untouched until the next session
  start (the running session is never reconfigured).
- NFR-12: both-theme + reduced-motion screenshots of the enrollment panel
  and the consent/pre-flight surfaces; axe clean; keyboard-only mint flow.

## Verification steps

1. `uv run pytest && uv run ruff check .` — includes the new enrollment,
   redeem, server-stamp, flag-not-drop, and grep-the-output tests.
2. `extension/`: `npm run check` green — connection-string, pairing machine,
   config-apply, consent-gate, and running-session-frozen tests.
3. `platform/`: `npm run build && npm run lint` green; no-raw-literal rule
   green.
4. End-to-end walkthrough, recorded: mint a batch → paste one string into a
   clean VS Code → consent → pre-flight → begin → events land server-stamped
   on the timeline and the dashboard status flips to `streaming`; then flip a
   toggle while the session runs and confirm the current session is unchanged
   and the new config applies only on the next session's pre-flight.
5. NFR-12 evidence archived for the new surfaces.
6. Confirm the four traceability rows and the Phase 19 tracker row are
   flipped only after 1–5 are green (golden rule 3).

## How this completes the platform loop (the anti-"side-feature" check)

Every piece of this phase is the *same* protocol continuing outward, not a
new subsystem beside it:

- The **token** is minted from the study's own `conditions` +
  `participants.planned` — it carries no new truth, only the protocol going
  live.
- The **capture config** is `instruments.*` run through the existing
  `derive` (wall #1) — the extension and the CLI produce identical settings;
  the IDE is now just another consumer of the document of record.
- The **consent statement** the participant sees is generated from the
  protocol (FR-AGENT-5) — pairing is the study's consent form reaching the
  person.
- The **events** carry the same join keys as every other leg (wall #4),
  now server-authoritative, and land on the one timeline the recipes,
  reports, and paper draft already consume — nothing downstream learns a new
  format.
- The **enrollment surface** lives inside the study workspace and feeds the
  existing live session-status view (FR-DASH-3), and every session records
  the `protocol_version` + `captureConfigVersion` it ran under — fixed for
  the whole session, never mutated mid-run — so a live study is replicable by
  construction (the platform's promise) down to exactly which metrics were on
  for each session.

Remove the LLM, the network, the dashboard — the CLI `derive` +
local-settings path still runs a session (wall #9). The link makes running a
study *self-serve and honest*; it invents no new source of truth.

## Deviations log

Record departures here and in `requirements/traceability.md` §3 as they
occur.

- **2026-07-19 → 2026-07-20, tasks C1–C3 committed, then execution stopped
  short of Slice D and E1.** The implementation plan
  (`docs/superpowers/plans/2026-07-19-live-capture-link.md`) never authored
  a distinct "Part D" for Slice D ("Session-boundary refresh + the deep
  link") — its session-boundary re-pull half landed inside task B6 and its
  deep-link half inside task B7, but the dashboard's "Open in VS Code"
  companion (the other side of that same deep link) was never built. Slice
  C's own spec line — "each paired/awaiting row shows the capture config
  that IDE will run under" — was also never carried into the plan's C1/C2
  task text, so `EnrollmentPanel` shipped with status chips only. FR-DASH-10's
  `streaming` status was explicitly deferred at task A4 review-fix time (a
  `paired`-only baseline, noted inline) but that deferral was never logged
  here or in traceability.md as golden rule 3 requires. Closed 2026-07-21 as
  tasks D1 (streaming-status derivation, joining the FR-DASH-3 live-session
  feed), D2 (the dashboard deep-link button), D3 (per-row capture-config
  visibility), and D4 (below) — before E1 ran, per golden rule 3.
- **Wall #6 verification is split between an automated unit test and a
  manual walkthrough, not one automated end-to-end test.** `src/core` stays
  `vscode`-free (`PROJECT_GUIDE.md`), and this repo has no `vscode`-mock test
  harness for adapter code (`extension/src/vscode/pairing.ts` calls real
  VS Code APIs) — building one was judged out of scope for this phase. Task
  D4 made the wall an explicit, unit-tested value
  (`shouldApplyCaptureConfig` in `src/core/captureConfig.ts`, proven by a
  full apply → mid-session-refuse → next-boundary-applies lifecycle test in
  `extension/test/captureConfig.test.ts`), but the literal fact that a
  *live, running* VS Code session's applied settings stay frozen while a
  toggle changes server-side is verified by the manual E1 Extension
  Development Host walkthrough (owner-run), not CI. NFR-12 evidence
  (both-theme/reduced-motion screenshots, axe, keyboard-only mint flow) is
  likewise captured manually as part of that same walkthrough rather than
  scripted. The four traceability rows are flipped only after that manual
  pass runs green, per golden rule 3 — this is a verification-method
  deviation, not a scope cut.
