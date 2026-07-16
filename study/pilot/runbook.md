# Pilot study facilitator runbook - pilot-2026 v1.0

Operates the frozen protocol `protocol/examples/pilot-study.yaml` (the
study's requirements specification - every step here is derived from it,
none of it is side-channel configuration). Facilitator: Idrees Razak.

Kit contents: this runbook · `participant-info-sheet.md` ·
`consent-form.md` · `ethics-application.md` · `tasks/` (A "expenses",
B "logbook") · `dry-run-report.md` (produced by the MP-08 dry run) ·
`findings.md` (framework post-mortem, grows during the study).

---

## 1. One-time setup (before any participant; done once at the dry run)

From a clean checkout on the facilitator laptop (macOS; needs Docker,
Node ≥ 20, uv, VS Code, Claude Code CLI):

```bash
uv sync --all-packages                  # Python workspace
(cd extension && npm ci && npm run package)   # builds cognitive-overlay-*.vsix
code --install-extension extension/cognitive-overlay-*.vsix
docker compose up -d --build            # middleware :8000 + demo seed
bash scripts/smoke.sh                   # full-stack proof; must exit 0
```

Then open **http://127.0.0.1:8000/** - the dashboard is served by the
middleware (one process). Confirm:

- [ ] Study overview shows `pilot-2026`, 5 RQs, planned 6 participants.
- [ ] Lifecycle board computes from artifacts (design gates green).
- [ ] Task board shows cards for every unsatisfied gate/instrument item.
- [ ] `bash scripts/smoke.sh` exited 0 (it prints `SMOKE OK`).

One **interactive dev-host pass** of the extension (start a session, answer
a fatigue probe, paste something, end the session, watch it land in the
live view) is required once before the first participant - the MP-05/MP-08
verifications exercised the compiled core against the live middleware, but
scripted, not through a human hand (recorded as finding DR-06).

## 2. The ethics gate (FR-ETH-1 - hard stop)

No real participant until the dashboard's lifecycle board shows the
`ethics` phase satisfied. That requires uploading, via the dashboard (or
`POST /ingest/files`):

- `ethics-approval.pdf` - the university's approval of
  `ethics-application.md` (submitted via the UoM CS ethics process;
  protocol field `study.ethicsRef` tracks the application).
- `consent-form.pdf` - the blank consent form as approved (per-participant
  signed copies are filed *outside* the framework, on paper/university
  storage - the ID↔identity mapping never enters the system, FR-ETH-3).

The lifecycle engine literally blocks `data-collection` until these exist -
this is the acceptance criterion, verified during the dry run (the study
correctly sat at `ethics` while dry-run data flowed, because ingest never
gates on lifecycle - NFR-1).

**Also before the first real session:** reset the store so demo/dry-run
rows cannot share it with participant data (the bundled demo uses roster
IDs P01/P02 and would blend silently - finding DR-05):

```bash
docker compose down -v && docker compose up -d --build middleware
```

then re-upload the gate artifacts (they live in the volume too).

## 3. Schedule and counterbalancing

Within-subjects, two 45-minute sessions per participant (≥ 15 min break or
different days), condition order × task pairing balanced in blocks of 4
(P05/P06 repeat the first two rows):

| Participant | Session 1 | Session 2 |
| ----------- | --------- | --------- |
| P01 | ai-assisted · Task A | unassisted · Task B |
| P02 | unassisted · Task A | ai-assisted · Task B |
| P03 | ai-assisted · Task B | unassisted · Task A |
| P04 | unassisted · Task B | ai-assisted · Task A |
| P05 | ai-assisted · Task A | unassisted · Task B |
| P06 | unassisted · Task A | ai-assisted · Task B |

Fill the actual schedule into `participant-schedule.md` and upload it - it
is the `recruitment` phase's gate artifact.

## 4. Per-session checklist

### Before the participant arrives (~10 min)

- [ ] Middleware healthy: `curl -s http://127.0.0.1:8000/health` shows
      `"studyId":"pilot-2026"`.
- [ ] Fresh copy of the session's task repo (per the table above) in a
      scratch workspace directory.
- [ ] Derive the instrument settings **from the protocol** into the task
      workspace (never hand-edit values):

      ```bash
      uv run protocol derive overlay-settings protocol/examples/pilot-study.yaml \
        --participant P0x --condition ai-assisted \
        > /path/to/task-workspace/.vscode/settings.json
      ```

- [ ] Condition setup: **ai-assisted** → Claude Code available in the
      integrated terminal; **unassisted** → Claude Code signed out/removed
      and all AI completion (Copilot etc.) disabled in VS Code.
- [ ] Signed consent form filed (paper, outside the framework).

### Session start

- [ ] Participant reads the task `README.md` (5 min, not counted).
- [ ] Run `Cognitive Overlay: Start Session`
      (`cognitiveOverlay.startSession`). The status bar shows the session
      id; note it on the schedule sheet.
- [ ] Start the wall clock: 45 minutes.

### During (never interrupt - NFR-1)

Monitor **only** through the dashboard live view (seq-gap warnings appear
there). Do not speak to the participant unless they stop the session or a
safety issue arises. Fatigue probes, stuck prompts, and the end survey are
the instruments' job, not yours.

### Session end (~5 min)

- [ ] At 45 min the overlay ends the session (or run
      `Cognitive Overlay: End Session`); the end survey (TLX debrief)
      appears - wait for the participant to finish it.
- [ ] Integrity: `curl -s http://127.0.0.1:8000/sessions/<sessionId>/gaps` -
      expect `"gaps":[]`. Any gap: check the local JSONL
      (`Cognitive Overlay: Open Data Folder` - it is the source of truth),
      re-POST it to `/ingest/events` (idempotent), re-check; document any
      residual gap as a finding.
- [ ] Static-metrics leg over the final workspace:

      ```bash
      # --out is a DIRECTORY; it receives function_metrics.jsonl and
      # file_metrics.jsonl (both get ingested; found at the dry run, DR-02)
      uv run python metrics/src/main.py /path/to/task-workspace \
        --participant P0x --condition <condition> --session <sessionId> \
        --timestamp <session-end-ISO> --format jsonl --out /tmp/m-<sessionId>
      uv run python - <<'PY'
      import json, urllib.request
      from pathlib import Path
      rows = [json.loads(l)
              for f in Path("/tmp/m-<sessionId>").glob("*_metrics.jsonl")
              for l in f.read_text().splitlines() if l]
      req = urllib.request.Request(
          "http://127.0.0.1:8000/ingest/metrics",
          data=json.dumps(rows).encode(),
          headers={"content-type": "application/json"}, method="POST")
      print(urllib.request.urlopen(req, timeout=10).read().decode())
      PY
      ```

      (MP-12 replaces this with shadow-git snapshot time series.)
- [ ] Setup friction, protocol ambiguities, anything hand-configured:
      `POST /findings` with the requirement ID it evidences (FR-META-1),
      and a line in `findings.md` §3.

## 5. After the last session

```bash
uv run analysis run protocol/examples/pilot-study.yaml   # per-RQ report
```

Upload `dataset-export.sqlite3` + `integrity-report.md` (data-collection
gates), then `per-rq-report.md` (analysis gate) via the dashboard. The
lifecycle board should now compute `analysis` → `write-up`; complete the
framework post-mortem in `findings.md` (§ template inside).

## 6. Incident playbook

| Incident | Response |
| -------- | -------- |
| Middleware down mid-session | Do nothing during the session (sinks are fire-and-forget; local JSONL keeps recording). Afterwards: restart compose, re-POST the session JSONL, verify gaps endpoint. |
| Participant withdraws | Stop the session; delete their rows via the middleware DB (documented, counted in findings.md); destroy the paper consent mapping per the info sheet. |
| Overlay probe never appears | Note it, do not interrupt; check `flags` and settings-derive output afterwards; file a finding against FR-INST-13. |
| Claude Code fails in ai-assisted session | Let the participant continue unassisted; mark the session `condition` as compromised in findings.md and exclude per-recipe (the honest call), never silently relabel. |
