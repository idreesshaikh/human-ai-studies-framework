# Phase 13: Ethics, privacy & operations

> Read first: `requirements/srs.md` §FR-ETH, §FR-OPS, `RUNBOOK.md`.
> **Satisfies:** FR-ETH-2/3, FR-OPS-1..7, NFR-1/5. **Status:** 🔶 partial.

## The idea

Privacy by construction and a $0 adoption path. Instruments capture no raw code,
keystrokes, or clipboard text: aggregates, shapes, and salted hashes only, with
two consent-matched scoped exceptions (agent-conversation content, workspace
snapshots). Participant data at rest stays on facilitator-controlled machines.
And the platform is *seeable and adoptable*: one container image, tagged
releases, a public seeded demo, Marketplace distribution, all runnable at $0 on
student-pack benefits.

## What it builds

- **Privacy (FR-ETH-2/3, NFR-5):** the content-free instrument discipline across
  all legs; anonymized participant IDs everywhere; the `redact.py` choke point
  for the one scoped exception; the assistant's aggregates-only boundary
  (FR-ETH-4, phase 09).
- **Operations (FR-OPS):** `railway.toml` + `middleware/Dockerfile` (one process
  serves API + the `platform/` build); Railway handles TLS, domains, and
  managed PostgreSQL; the release pipeline (`.github/workflows/release.yml`,
  `deploy.yml`) → GHCR image → Railway redeploy; on-demand SonarQube
  (`docker-compose.yml --profile sonar` / Azure deallocated VM) for cognitive
  complexity; the pluggable auth seam (`middleware/auth.py`: none / token /
  clerk) with `GET /auth/config`.

## Remaining

- Hosting/account provisioning (Railway/Clerk/Marketplace) and the first
  tagged release; per-user profiles (FR-OPS-7) once Clerk is provisioned.

## Verification

- `uv run pytest`: the privacy boundaries (grep-the-output on instrument and
  assistant output); `docker build -f middleware/Dockerfile .` succeeds;
  `scripts/smoke.sh` green from a clean bring-up.
