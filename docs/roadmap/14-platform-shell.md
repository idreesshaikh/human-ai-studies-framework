# Phase 14: Platform Shell + Hero

> Self-contained: execute this file in a fresh session at the repo root.
> Read first: `docs/VISION.md`, `requirements/specs/fr-plat.md` (the
> requirement of record), `requirements/specs/nfr-12-experience.md`,
> `docs/design/ui-motion-spec.md`, `docs/design/data-model.md`,
> `docs/design/architecture.md`, `requirements/build-vs-adopt.md`
> D25/D26/D29/D34/D37, and `docs/roadmap/README.md` (the walls + the
> autonomy charter, both bind this phase).

**Depends on:** Phase 15 slice 1 (the `platform/` app exists and hosts the
conversation surface this shell will wrap), Phase 04 (middleware), Phase 13 /
FR-OPS-5 (the auth seam: `none`/`token`/`clerk`, Clerk provisioned).
**Satisfies:** FR-PLAT-1..5; completes FR-OPS-5/7; lays the NFR-12
foundation every later surface inherits. **Elicited:** owner, Phase 01
rev 8 ("multi-researcher platform… projects, roles, hero").
**Status:** Built (2026-07-18): logic, tests, and build green; the
in-browser NFR-12 evidence (screenshot pairs + axe) is the one remaining
acceptance step, noted below.

## The idea

Turn the single-facilitator engine into a **multi-researcher platform**
without breaking the single-facilitator experience. Concretely: projects
scope everything; roles gate everything server-side; invitations bring
colleagues in; a hero page makes a stranger (S7) understand and *touch*
the product inside three interactions; and a self-hosted `none`-mode
boot remains byte-for-byte today's experience. The conversation surface
built in Phase 15 slice 1 re-homes into the project shell; after this
phase, "open the design conversation" is something that happens *inside
a project you belong to*.

Non-negotiable bounds, inherited verbatim:

- **Scoping is one choke point** (FR-PLAT-1): project checks live in the
  middleware query layer, not per-route ad hoc, testable by
  construction, like the FR-ETH-4 boundary.
- **No permission check exists only in the frontend** (FR-PLAT F2.3).
  The UI reflects the matrix; the server enforces it.
- **Ingest stays unauthenticated** (NFR-1): sensors are fire-and-forget;
  rows bind to projects via the study, unknown rows land flagged
  (FR-ING-6).
- **Self-hosted continuity** (FR-PLAT-5): `none`/`token` modes run
  project-free with one implicit project: a real row, invisible in UI;
  the existing smoke test must pass unchanged.
- **PostgreSQL stays** (D26): scoping is a column + an index, not a database
  migration adventure.

## Slices

### Slice A: Data layer + the scoping choke point (FR-PLAT-1/2)

Backend only; no UI change; the existing dashboard keeps working throughout.

1. **Tables** (names per `docs/design/data-model.md`):

   ```sql
   project(id TEXT PK, name TEXT, slug TEXT UNIQUE, createdBy TEXT,
           createdAt TEXT)
   membership(projectId REFS project, identitySub TEXT, role TEXT
              CHECK(role IN ('owner','researcher','viewer')),
              invitedBy TEXT, joinedAt TEXT,
              PRIMARY KEY (projectId, identitySub))
   invitation(id TEXT PK, projectId REFS project, email TEXT,
              role TEXT, token TEXT UNIQUE, expiresAt TEXT,
              acceptedAt TEXT NULL)
   -- plus: ALTER TABLE study ADD COLUMN projectId REFS project;
   -- index on study(projectId); every study-scoped join inherits it.
   ```

2. **Boot migration**: on first start after upgrade, create the default
   project (slug `default`), adopt every orphan study into it, emit one
   loud log block stating exactly what moved. Additive and safe → it
   runs without asking, but it *announces itself* (the Phase 12 stale-DB
   posture, relaxed only because nothing is destroyed).

3. **The choke point**: one FastAPI dependency, one module
   (`middleware/src/middleware/authz.py`):

   ```python
   def require_project(min_role: Role) -> Depends:
       """Resolve (identity, projectId) -> Membership or 403.
       Every project-scoped router depends on this; greppable;
       no route re-implements the check."""
   ```

   The permission matrix from `fr-plat.md` §2 is data (a dict), not
   prose: `CAPABILITIES = {"apply_draft": Role.RESEARCHER, "freeze":
   Role.OWNER, ...}`; tests iterate the dict, so adding a capability
   without tests is impossible by construction.

4. **Tests**: parameterized pytest over (route × role): every matrix
   cell gets its positive and negative case (F2.1); a `viewer` token
   replaying a captured `researcher` request set gets uniform 403s with
   plain-language bodies (F2.2); a grep/route-audit test asserts every
   project-scoped router carries the dependency (F2.3).

### Slice B: Identity completion (FR-OPS-5/7, FR-PLAT-5)

1. `clerk` mode: verified JWT `sub` → membership lookup; sign-up flow
   creates the identity but *no* project (projects are explicit acts).
2. `none`/`token` modes: the **implicit project**, a real row (slug
   `implicit`), auto-membership as `owner`, all project UI unmounted.
   One code path everywhere; zero conditionals like `if multi_tenant`.
3. Session identity surfaces in one place (`GET /me`: sub, display
   name, memberships) so both SPAs share it.
4. Fit gate: the existing smoke test runs unchanged against a
   `none`-mode boot of the full stack (FR-PLAT-5's criterion).

### Slice C: The shell UI (`platform/`)

The React app grows from "a conversation surface" into "a product with
rooms". Routes (React Router; layout components per D37 substrate):

```
/                      hero (public)
/demo                  the shared demo project, viewer role (public)
/projects              project list + create        (signed in)
/p/{slug}              project home: studies, activity, members preview
/p/{slug}/studies/{id} study home: conversation (Phase 15) mounts here
/p/{slug}/members      members table + invitations  (owner sees controls)
/p/{slug}/settings     rename, danger zone           (owner)
```

Component inventory (shadcn base, tokens only, no raw literals):

| Component | Notes |
| --- | --- |
| `AppFrame` | sidebar (projects, studies) + top bar (breadcrumb, theme toggle, account); collapses to a sheet on narrow viewports |
| `ProjectSwitcher` | command-palette style (⌘K), fuzzy over project names; creating a project is the palette's empty-state action |
| `MembersTable` | precise register; optimistic role edits (NFR-12 §3.3) with server reconciliation; role chips are static: roles are facts |
| `InviteDialog` | email + role picker; **copy-link is the primary affordance**, email delivery is the optional enhancement (see freedom note); expiry stated in plain language |
| `InviteAccept` | the landing route for a token: sign-in (if needed) → join → drop into the project with the avatar-bounce moment (`ui-motion-spec.md` §5) |
| `RoleGate` | render-prop helper reflecting the server matrix; exists for UX only; the server remains the enforcement |
| `EmptyState`s | every new view teaches: project list empty → "Research is better with witnesses. Create your first project."; members empty → invite action |

Interaction notes (binding): role edits are optimistic; invitation
acceptance is the *one* warm-register moment in the shell; everything
else in members/settings is precise register. Keyboard: the switcher,
tables, and dialogs are fully traversable; focus rings per tokens.

### Slice D: Hero + the shared demo (FR-PLAT-4)

The public front. Content contract (copy is yours, see freedoms, but
these elements exist):

1. **The one-liner** and a single sentence of what happens here, in
   NFR-11 plain language (zero requirement IDs, zero jargon).
2. **The product demonstrating itself**: an embedded, *live* design
   conversation running the Phase 15 deterministic demo script (zero LLM
   key, zero backend needed; the stub is the degradation path doing
   double duty as marketing). The visitor watches design moves arrive,
   can accept/reject them, sees the draft rail fill.
3. **One-click demo project**: a public, seeded, read-only (`viewer`)
    project everyone shares, reseeded on boot (D26 Railway posture, the
   existing seeding mechanism extended). Hero → demo project → rendered
   per-RQ report in **≤ 3 interactions, no account** (F4 fit).
4. Sign-up CTA (Clerk) → first project → designer open in ≤ 2 minutes.
5. `scripts/seed_demo.py` (or a `DEMO_MODE` boot flag, builder's
   choice) produces the demo project deterministically: demo study,
   completed conversation with grounded moves, compiled protocol,
   recipes run, report rendered.

### API surface (Slice A–D, REST + role checks per the matrix)

```
POST   /projects                          create (any signed-in identity)
GET    /projects                          my memberships
GET    /projects/{p}                      project home payload
PATCH  /projects/{p}                      rename (owner)
DELETE /projects/{p}                      delete (owner; requires typed confirm)
GET    /projects/{p}/members              list
PATCH  /projects/{p}/members/{sub}        role change (owner)
DELETE /projects/{p}/members/{sub}        remove (owner; last owner refuses)
POST   /projects/{p}/invitations          create (owner) → {token, url}
DELETE /projects/{p}/invitations/{id}     revoke (owner)
POST   /invitations/{token}/accept        join (signed-in; single-use; expiring)
GET    /me                                identity + memberships
GET    /demo                              demo project pointer (public)
```

Every study-bound legacy endpoint gains the project prefix through the choke
point; the Svelte console (frozen) keeps its paths working via the
implicit/default project until per-view parity retires it (D34).

## Degrees of freedom

Beyond the charter in `README.md`, specifically free in this phase:

- **Hero art direction**: the constellation motif is *suggested* (it's
  the signature surface); any direction that passes the S7 hallway test
  and the token/contrast gates is acceptable. Go weird; measure it.
- **Email delivery**: pluggable provider with copy-link fallback is the
  requirement; *which* provider (or shipping copy-link-only in this
  phase) is yours. A provider adoption needs its D-row.
- **Navigation anatomy**: sidebar vs. top-nav vs. hybrid; the routes
  and the ⌘K switcher are fixed, the chrome is not.
- **Demo study content**: any of the trial studies works as the seeded
  demo; pick the one that renders the most beautiful report.
- **Project-home layout**: what "activity" shows, how studies are
  carded, and whether members preview inline are yours within the registers.

## Acceptance (maps to fit criteria)

- FR-PLAT-1: migration adopts orphans loudly; cross-project reads
  provably impossible (test hits another project's study by ID → 403/404).
- FR-PLAT-2: F2.1 matrix-complete tests; F2.2 uniform-403 replay; F2.3
  no frontend-only checks.
- FR-PLAT-3: invited researcher lands with correct powers; expired/used
  token fails with a human explanation.
- FR-PLAT-4: hero → report ≤ 3 interactions without an account; sign-up
  → designer ≤ 2 minutes (walkthrough, timed).
- FR-PLAT-5: the existing smoke test green on `none`-mode boot.
- NFR-12: token audit (F1), both-themes + reduced-motion screenshot
  pairs (F2), axe clean on hero/projects/members (F3), keyboard-only
  invite-accept walkthrough (F5).

## Verification steps

1. `uv run pytest && uv run ruff check .`: includes the new
   matrix-parameterized authz suite.
2. `platform/`: `npm run build && npm run lint` green; no-raw-literal
   rule green.
3. Demo walkthroughs, recorded: (a) hero → demo report, counting
   interactions; (b) sign-up → project → conversation open, timed;
   (c) invite flow end to end including expiry and reuse failure;
   (d) `none`-mode boot + the existing smoke test.
4. NFR-12 evidence archived (screenshots both themes + reduced-motion,
   axe report).

## Deviations log

Record departures here and in `requirements/traceability.md` §3.

**2026-07-18: built.** What landed and where it differs from the spec:

- **Slices A + B (backend) were already present** (data model, boot
  migration, the `authz` choke point, the auth seam with the widened
  `Identity`, and all endpoints in the API surface). This pass *completed*
  them: added the `ROLES` constant the members/invitation endpoints
  referenced but that was undefined (a latent crash); made the study choke
  point preserve the permissive-sink contract in `none`/`token` mode when
  no protocol is loaded, so FR-PLAT-5's "smoke test unchanged" holds
  (`test_no_protocol_means_accept_all` was regressing to 404); and cleaned
  the pre-existing lint in the touched backend files.
- **Slice A tests** landed as `middleware/tests/test_authz.py`: the matrix
  is verified by iterating `CAPABILITIES` (so a new capability can't ship
  untested); plus uniform-403 replay, a route audit that every
  project/study route carries the choke point, cross-project refusal, boot
  migration adopting an orphan study, single-use + expiring invitations,
  and last-owner refusal. Full middleware suite: 78 passing.
- **Slices C + D (frontend)** built in `platform/`: react-router routes,
  `AppFrame` (sidebar + top bar, collapsing), the ⌘K `ProjectSwitcher`,
  `MembersTable` (optimistic role edits), `InviteDialog` (copy-link
  primary), `InviteAccept`, `RoleGate`, `EmptyState`, and the pages
  (hero, demo, projects, project home, study, members, settings). New
  dependencies decided in D38.
- **Data layer deviation:** the shell talks to the API through a small
  typed client (`lib/api.ts`) with a plain `fetch`; an in-memory backend
  stands in when `VITE_API_BASE` is unset, so the whole shell (and the
  hero's live demo) runs offline. This doubles as the verify harness
  (`scripts/verify-shell.mjs`) and is why no data-fetching library was
  adopted yet (D38).
- **Not yet done (needs a running stack + browser):** the seeded demo
  project on the *server* (`scripts/seed_demo.py` / `DEMO_MODE`): the
  frontend demo currently runs on the in-memory fake; the timed hero→report
  and sign-up walkthroughs; and the NFR-12 evidence archive (both-theme +
  reduced-motion screenshots, axe on hero/projects/members). The Clerk
  sign-up UI is stubbed (the account menu's "Sign out" is inert) pending
  the hosted-auth wiring.
