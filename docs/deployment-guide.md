# Deployment guide — step by step, zero to running

A literal, checkbox-able walkthrough for taking a clean checkout of PHOENIX
to a live, public Railway deployment. This expands
[`RUNBOOK.md` §9](../RUNBOOK.md) into an ordered template you can follow
top to bottom; RUNBOOK stays the reference summary, this is the "first
time doing it" version. Everything here is $0 (GitHub Student Pack tier);
no step requires a paid plan.

The design (per `CLAUDE.md`): **one container image** (middleware serves
the API and the built SPA on one process, NFR-7), **Railway** owns
compute + TLS + domains, **Railway PostgreSQL** owns the database, **GHCR**
holds the built image, **GitHub Actions** wires CI → image → redeploy.
Nothing here touches a VM, Caddy, or manual SSH.

---

## Phase 0 — accounts (5 min)

- [ ] GitHub account with this repo forked or pushed under your own account
- [ ] [railway.app](https://railway.app) account (sign in with GitHub — this
      also grants Railway read access to deploy from the repo)
- [ ] *(optional, recommended)* [clerk.com](https://clerk.com) account —
      only needed if you want hosted sign-in (`MIDDLEWARE_AUTH=clerk`);
      skip this phase entirely and use `MIDDLEWARE_AUTH=token` if you just
      want the fastest path to a running instance

---

## Phase 1 — prove it locally first (10 min)

Don't deploy something you haven't run. From a clean checkout:

- [ ] `uv sync --all-packages`
- [ ] `docker compose up` — boots PostgreSQL + the middleware, serves the
      platform build at `http://localhost:8000`
- [ ] Open `http://localhost:8000` — you should see the seeded demo study
- [ ] `Ctrl-C`, `docker compose down` when satisfied

If this doesn't work locally, it won't work on Railway either — the
container is the same artifact in both places.

---

## Phase 2 — (optional) stand up Clerk auth

Skip this whole phase if you're using `MIDDLEWARE_AUTH=token` instead —
jump to Phase 3.

- [ ] Clerk dashboard → **Create application** → name it, enable your
      preferred sign-in methods (email is enough to start)
- [ ] Clerk dashboard → **API Keys** → copy the **Publishable key**
      (`pk_live_...` or `pk_test_...`) → this becomes
      `MIDDLEWARE_CLERK_PUBLISHABLE_KEY`
- [ ] Note your Clerk **Frontend API URL**, shown on the same page — it
      looks like `https://<your-app>.clerk.accounts.dev` (dev) or your
      custom domain (prod). From it:
      - `MIDDLEWARE_CLERK_ISSUER` = that URL exactly
      - `MIDDLEWARE_CLERK_JWKS_URL` = that URL + `/.well-known/jwks.json`
- [ ] Keep these three values handy for Phase 4 — the middleware verifies
      Clerk session JWTs against the JWKS URL; nothing else needs
      configuring on the Clerk side for a first deployment

---

## Phase 3 — create the Railway project

- [ ] [railway.app](https://railway.app) → **New Project** → **Deploy from
      GitHub repo** → pick this repo
- [ ] Railway auto-detects `railway.toml` at the repo root (build =
      `middleware/Dockerfile`, context = repo root, start command =
      `sh middleware/scripts/start_with_seed.sh`, healthcheck = `/health`)
      — do not override these; if Railway asks, confirm the Dockerfile
      path is `middleware/Dockerfile`
- [ ] In the same project, **+ New** → **Database** → **Add PostgreSQL** —
      Railway injects `DATABASE_URL` into the middleware service
      automatically; you never set this by hand
- [ ] Service → **Settings** → **Volumes** → **New Volume** → mount path
      `/data`. **Do not skip this** — without it, every uploaded consent
      PDF or paper PDF is silently lost on the next redeploy or restart
      (only the file's hash/path lives in Postgres; the bytes need the
      volume). Postgres needs no equivalent step, its plugin manages its
      own storage.

---

## Phase 4 — environment variables

Service → **Variables**. Set:

| Variable | Required? | Value |
| -------- | ---------- | ----- |
| `MIDDLEWARE_AUTH` | yes | `clerk` (if you did Phase 2) or `token` |
| `MIDDLEWARE_TOKEN` | if `auth=token` | a long random string (`openssl rand -hex 32`) |
| `MIDDLEWARE_CLERK_JWKS_URL` | if `auth=clerk` | from Phase 2 |
| `MIDDLEWARE_CLERK_ISSUER` | if `auth=clerk` | from Phase 2 |
| `MIDDLEWARE_CLERK_PUBLISHABLE_KEY` | if `auth=clerk` | from Phase 2 |
| `MIDDLEWARE_SEED_ON_START` | recommended for a first deploy | `1` — reseeds the demo study on every boot so there's always something to look at |
| `MISTRAL_API_KEY` | optional | enables the LLM-backed design conversation/knowledge assistant; everything still works without it (degraded, deterministic path) |
| `MIDDLEWARE_S2_API_KEY` | optional | Semantic Scholar enrichment for the literature corpus |
| `MIDDLEWARE_GITHUB_TOKEN` | optional | needed only for the curated-mining (GitHub) leg's live source |

`DATABASE_URL` — do not set manually; the PostgreSQL plugin already injected it in Phase 3.

- [ ] All required variables set → **Deploy** (Railway triggers the first
      build automatically once variables are saved)

---

## Phase 5 — wire CI to auto-redeploy on every green `main`

This step makes `git push` to `main` end in a live redeploy, with no
manual Railway click after today.

- [ ] Railway → service → **Settings** → copy the **Service ID** (from the
      URL, `/service/<id>`, or the settings panel)
- [ ] Railway → **Account Settings** → **Tokens** → create a token → copy
      it (shown once)
- [ ] *(optional)* Railway → environment settings → copy the
      **Environment ID** if you're not deploying to the default environment
- [ ] GitHub repo → **Settings** → **Secrets and variables** → **Actions**
      → add:
      - `RAILWAY_API_TOKEN`
      - `RAILWAY_SERVICE_ID`
      - `RAILWAY_ENVIRONMENT_ID` (optional)
- [ ] Push anything to `main` (or re-run the `CI` workflow) → confirm the
      `Deploy demo` workflow (`.github/workflows/deploy.yml`) runs after
      CI goes green, builds the image, pushes to
      `ghcr.io/<owner>/<repo>/middleware`, and triggers the Railway
      redeploy (check the Actions tab — a skipped/failed step here means a
      secret is missing or misnamed, not a code problem)

---

## Phase 6 — verify the live deployment

- [ ] Open the Railway-assigned URL (service → **Settings** → **Networking**
      → **Generate Domain** if you haven't already) — the platform should
      load, same as your local `docker compose up` check in Phase 1
- [ ] `curl https://<your-domain>/health` → `200`
- [ ] If `MIDDLEWARE_SEED_ON_START=1`, confirm the seeded demo study is
      visible in the UI
- [ ] If you configured Clerk, confirm sign-in works end to end

---

## Phase 7 — (optional) custom domain

- [ ] Railway → service → **Settings** → **Domains** → **Custom Domain** →
      enter your domain → add the shown CNAME/A record at your DNS
      provider. Railway provisions and renews TLS automatically — no
      Caddy, no manual certificates.

---

## Troubleshooting checkpoints

| Symptom | Likely cause |
| ------- | ------------ |
| Build fails on Railway but `docker compose up` worked locally | Check the build is using `middleware/Dockerfile` with repo-root context (see `railway.toml`) — a wrong build context is the most common mismatch |
| Uploaded PDFs vanish after a redeploy | The `/data` volume from Phase 3 wasn't attached, or was attached to the wrong path |
| `MIDDLEWARE_AUTH=clerk` requests get 401/503 at startup | `MIDDLEWARE_CLERK_JWKS_URL` missing or wrong — the service fails loudly by design (never "quietly open") rather than silently accepting requests |
| `Deploy demo` Action shows "skipping Railway deploy" | `RAILWAY_API_TOKEN` or `RAILWAY_SERVICE_ID` GitHub secret is unset or misnamed |
| Demo has no data after a fresh deploy | `MIDDLEWARE_SEED_ON_START` not set to `1` |

---

## What this does *not* cover

- SonarQube (cognitive-complexity metric) — runs separately, on-demand,
  never on Railway: `docker compose --profile sonar up` locally, or the
  Azure VM workflow (`.github/workflows/sonar-vm.yml`). Not part of the
  live deployment.
- The VS Code extension — distributed as a `.vsix` via GitHub Releases on
  version tags, not deployed anywhere (see `RUNBOOK.md` §9.2 for cutting a
  release).
