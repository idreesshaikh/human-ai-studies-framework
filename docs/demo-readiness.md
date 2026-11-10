# Verification

Requires Python 3.12+, Node.js 22+, and uv. Install locked dependencies and
Chromium from the repository root:

```bash
uv sync --all-packages --group docs --frozen
npm --prefix platform ci
npm --prefix extension ci
npm --prefix platform exec playwright install chromium
uv run --no-sync python scripts/check_demo.py
```

The gate runs Python lint, workspace configuration checks, tests with the 79%
coverage floor, the separate 95% metrics floor, extension checks, the frontend
build and browser workflows, and a strict documentation build. A failed or
interrupted run is never marked successful.

Logs and `report.json` go to ignored `.research-artifacts/demo-readiness/`.
The report records the commit, source fingerprint, tool versions, exact commands,
timings, and exit codes. Use `--artifacts /tmp/studyloop-verification` to choose
another location. Checks use disposable storage and synthetic fixtures.

## Browser checks

```bash
node platform/scripts/ui-regression.mjs --audit --screenshots /tmp/studyloop-screenshots
```

The suite covers empty and populated views, protocol review, manual entry,
enrollment, planning, downloads, permissions, themes, and responsive layouts.
Recovery cases include interrupted chat, retry identity, Stop, Unicode,
HTML-looking input, and duplicate submission. Review screenshots for personal
information before publishing them.

Automated Chromium accessibility checks complement manual keyboard and
assistive-technology checks. They do not establish compatibility with every
browser or editor version.

## Example and model checks

Use the [disposable example](demo-walkthrough.md) to inspect the workflow.
For optional provider compatibility:

```bash
uv run --no-sync --env-file .env python scripts/check_design_models.py --live
```

This explicitly calls a provider using synthetic briefs and checks parser and
compiler behavior. It does not measure advice quality or empirical usefulness.

Check current dependency advisories separately:

```bash
npm --prefix platform audit --audit-level=high
npm --prefix extension audit --audit-level=high
```

Extension unit tests do not replace installing TERN in the intended VS Code
version, reviewing consent, pairing a separate study, and completing a session.
Statistical and capture assumptions are documented in the
[planner guide](planner.md) and [scope](scope.md).
