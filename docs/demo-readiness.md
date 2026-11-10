# Demo rehearsal and verification

Use Python 3.12+, Node.js 22+, and uv. Install the locked dependencies and
Chromium from the repository root:

```bash
uv sync --all-packages --group docs --frozen
npm --prefix platform ci
npm --prefix extension ci
npm --prefix platform exec playwright install chromium
```

## Run the complete software gate

```bash
uv run --no-sync python scripts/check_demo.py
```

The command runs Python lint, workspace configuration checks, the entire
workspace test suite with the 79% coverage floor, the separate 95% metrics
coverage floor, extension checks, the production frontend build and browser
accessibility/workflow checks, and the strict documentation build. It returns
nonzero if any gate fails and continues collecting the other results.

Logs and `report.json` go to ignored `.research-artifacts/demo-readiness/`.
The report records the commit, branch, dirty state, source fingerprint, runtime
versions, exact commands, timings and exit codes. An interrupted run is never
marked complete. It contains no environment-variable dump or credentials.
Use `--artifacts /tmp/studyloop-verification` to choose another location.

These checks use synthetic fixtures and disposable storage. No live language
model, participant database, paper service or deployment is needed. Current
dependency advisories require network access and are checked separately:

```bash
npm --prefix platform audit --audit-level=high
npm --prefix extension audit --audit-level=high
```

For reviewable browser screenshots:

```bash
node platform/scripts/ui-regression.mjs --audit --screenshots /tmp/studyloop-screenshots
```

The browser suite covers empty and populated views, protocol review and manual
entry, enrollment, planning, downloads, long literature records, read-only
permissions, light/dark themes, and desktop/tablet/mobile widths. Recovery cases
include failed and interrupted chat streams, retry identity, Stop, Unicode and
HTML-looking text, and duplicate form submission. Automated accessibility
checks complement human keyboard and assistive-technology review.

## Rehearse in a separate demo database

Run these commands in the same terminal. The directory is new and contains
only the labelled example, keeping rehearsal separate from collected data.

```bash
DEMO_DATA_DIR="$(mktemp -d "${TMPDIR:-/tmp}/studyloop-demo.XXXXXX")"
export MIDDLEWARE_DB="$DEMO_DATA_DIR/middleware.sqlite3"
export MIDDLEWARE_DATA_DIR="$DEMO_DATA_DIR"
export DATABASE_URL="" MIDDLEWARE_AUTH=none MIDDLEWARE_PROTOCOL=""
export MIDDLEWARE_CORPUS_BOOTSTRAP=0 MIDDLEWARE_REFRESH_INTERVAL_H=""
npm --prefix platform run build
uv run --no-sync python -m middleware seed-example
uv run --no-sync python -m middleware
```

Open `http://127.0.0.1:8000`, then the study named
**Example: Copilot and bug fixing (synthetic data)**. Inspect Setup, the saved
Plan, participant links and Data. Show the synthetic notice, incomplete
sessions, sequence gaps and control-arm signals. Export a data bundle and
explain why the simulated sessions are excluded by default. Run the seed
command again to confirm that it creates no duplicate study.

Create a separate empty study to demonstrate the checklist/template path.
Describe two coding conditions, enter participants and outcomes, review the
compiler-validated draft and apply it. An unconfigured model should produce
an explicit connection message while the checklist remains usable.

For a configured provider, run the bounded synthetic compatibility check:

```bash
uv run --no-sync --env-file .env python scripts/check_design_models.py --live
```

This explicitly makes provider calls and records parsing/compiler behavior;
it does not measure the quality of methodological advice. Freeze exact model
versions for a research comparison. Inspect the report before presenting a
live chat; account limits and provider availability can change.

## Remaining environment checks

The browser gate uses Chromium and SQLite. A packaged VSIX and unit tests do
not replace installing the extension in the intended VS Code version,
pairing it with the demo study, obtaining consent and completing a session.
Verify Firefox/WebKit, assistive technology, PostgreSQL, the Docker image and
the deployed public URL when those are part of the presentation environment.
See [the WSESE evidence requirements](wsese-2027-readiness.md) before making
claims about research quality or validated instruments.
