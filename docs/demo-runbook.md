# Local rehearsal

Use a rehearsal study to check the whole path: choose a design, approve its
capture scope, run TERN, and inspect the exported data. A successful rehearsal
checks the plumbing; it is not evidence for a research claim.

## Start locally

Follow the [setup instructions](../README.md#run-locally), including building
the platform and extension. Keep rehearsal data separate from participant data:

```bash
REHEARSAL_DIR=$(mktemp -d)
MIDDLEWARE_DB="$REHEARSAL_DIR/study.sqlite3" uv run python -m middleware backup-seed
MIDDLEWARE_DB="$REHEARSAL_DIR/study.sqlite3" uv run python -m middleware
```

Keep the directory path if you want to resume this rehearsal. Open
[localhost:8000](http://localhost:8000) and find **My project** →
**ai-cognitive-load-demo**. The backup seed provides an owned study with an
approved protocol. The separate public demo project is read-only.

Add `--env-file .env` to `uv run` if you have configured a model key there.
The seed is useful for testing capture without a model key. To test design
instead, start a new study from **Repertoire**, review its instruments and
analysis plan, and approve the protocol. Model-assisted conversation needs
`MISTRAL_API_KEY`; it does not replace the researcher's methodological review.

## Run a participant session

1. In the study, open **Run → Enrollment** and mint a participant link.
   Review its capture switches. Leave external producers off unless they are
   part of the session you intend to test.
2. Open `extension/` in VS Code and press **F5**. In the development host,
   open `extension/examples/tern-lab`.
3. Run **TERN: Connect to Study**, paste the link, and review consent and the
   capture pre-flight. Treat the link as a credential; keep it out of slides,
   logs, and commits.
4. Run **TERN: Start Study Session**. Edit and save `sample_app.py`, switch
   focus, scroll, and use **TERN: Log Fatigue Now**.
5. End the session and complete the debrief. Inspect the local JSONL under
   the workspace's `.study-data/` directory before relying on the server copy.

Normal editor capture records measurements, timings, and hashed identifiers,
not source code or clipboard text. Workspace snapshots and transcript content
are separate, explicit capture choices; review their policies before enabling
them. See the [capture guide](../extension/docs/development.md).

## Inspect the handoff

Return to **Data**. Check that the session belongs to the intended study, its
condition and task are correct, and any sequence gaps are understood. Download
the protocol, JSON dataset, and starter notebook. The notebook describes the
data and the registered analyses; it is not a completed confirmatory analysis.

A **synthetic dry run** exercises the ingest and analysis path without TERN.
New simulated rows carry `synthetic: true` in their payload. They remain in the
study's exports, so run simulations only in a separate rehearsal study or
exclude them explicitly before analysing participant data. The dry-run summary
uses only the sessions created by that run.

The [worked example](examples/pilot-2026/notebook.ipynb) is a checked-in,
reproducible starting point. To exercise the API-to-analysis path automatically:

```bash
# With the local server already running:
SMOKE_NO_COMPOSE=1 bash scripts/smoke.sh
```

The smoke test creates its own synthetic study, checks duplicate and gap
handling, and exports a report and notebook to a temporary directory. It prints
the retained study ID and artifact path. Use a development server, not a live
participant deployment.

## Troubleshooting

- **No model configured:** use a template or the seeded approved protocol.
- **Permission denied:** use an owned study; the public demo is read-only.
- **Cannot connect:** check the server address and port in the participant link.
- **No mirrored events:** inspect the local JSONL and
  [TERN troubleshooting](../extension/docs/troubleshooting.md).
- **No automatic probe yet:** use the manual fatigue command. Do not shorten
  thresholds during a real participant session without amending the protocol.
