# FR-PLAT — Platform shell: projects, roles, hero (detailed specification)

**SRS family:** FR-PLAT. **Phase:** MP-14. **Spec v1, 2026-07-17.**
Surface built per D34 (React 19 + Vite + Tailwind + shadcn/ui, the new
`platform/` app) under NFR-12; identity per FR-OPS-5/7 (Clerk provisioned).

## 1. Data model (FR-PLAT-1, M)

```
project(id, name, slug, createdBy, createdAt)
membership(projectId, identitySub, role, invitedBy, joinedAt)
invitation(id, projectId, email, role, token, expiresAt, acceptedAt?)
study.projectId  -- every study, paper set, curated dataset, conversation
                 -- and finding is project-scoped; no cross-project reads
```

- Project scoping is enforced in the middleware query layer (every
  study-bound endpoint gains the project check), not per-route ad hoc —
  one choke point, testable by construction (the FR-ETH-4 pattern).
- SQLite stays (D11): scoping is a column + index, not a database swap;
  Postgres remains the recorded config-swap escape hatch.
- Existing single-study data migrates into a default project on first
  boot after upgrade (loud, logged, reversible — the MP-12 stale-DB
  posture: fail loudly, never migrate silently... here migration is
  additive and safe, so it runs, but announces itself).

## 2. Roles & enforcement (FR-PLAT-2, M)

Permission matrix (server-side, UI merely reflects it):

| Capability | owner | researcher | viewer |
| --- | --- | --- | --- |
| View studies, reports, conversations | ✓ | ✓ | ✓ |
| Contribute conversation turns / design moves | ✓ | ✓ | — |
| Apply compiled drafts (pre-freeze) | ✓ | ✓ | — |
| Freeze protocol; approve post-ethics amendments | ✓ | — | — |
| Run mining jobs; upload gate artifacts | ✓ | ✓ | — |
| Manage members, roles, invitations | ✓ | — | — |
| Delete study / project | ✓ | — | — |

Ingest stays unauthenticated (NFR-1: sensors are fire-and-forget) but
session join keys bind rows to a project via the study; unknown rows
keep landing flagged (FR-ING-6). Fit criteria: F2.1 every matrix cell
has a positive + negative API test; F2.2 a `viewer` token replaying a
`researcher` request set gets uniform 403s with plain-language bodies;
F2.3 no permission check exists only in the frontend (grep + route
audit).

## 3. Invitations (FR-PLAT-3, S)

Email-link invitations (role pre-assigned, expiring token, single-use);
accepting routes through sign-in (FR-OPS-5) then binds `sub` →
membership. Email delivery is a pluggable provider with a copy-link
fallback (self-hosted instances need zero email config — the FR-OPS-5
no-third-party-required posture). Fit: an invited `researcher` lands in
the project with correct powers; an expired/used token fails with a
human explanation.

## 4. Hero page & first-run (FR-PLAT-4, S)

The public front: what the platform is (the one-line vision), the
conversation-first designer shown, one-click entry to the live seeded
demo project (read-only `viewer` on a demo everyone shares), sign-up.
Copy follows NFR-11 (zero requirement IDs, plain language); design
follows NFR-12; content is the v2 vision's "S7's first minute" — the
platform must *demonstrate* itself (the demo study, the beautiful
report) rather than describe itself. Fit: an S7-profile tester reaches
a rendered study report from the hero in ≤ 3 interactions without an
account; sign-up → first project → designer open in ≤ 2 minutes.

## 5. Self-hosted continuity (FR-PLAT-5, S)

`none`/`token` auth modes run project-free: one implicit project, no
hero/sign-up surfaces mounted, dashboards land directly on the study —
byte-for-byte today's single-facilitator experience. The implicit
project is a real row (so code has one path), invisible in UI. Fit:
the existing smoke test passes unchanged against a `none`-mode boot of
the v2 stack.
