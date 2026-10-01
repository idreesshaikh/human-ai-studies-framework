# Verifying the TERN and platform integration (#64)

I wanted to confirm that a study designed on the platform, captured by the TERN
extension, and fed back for analysis holds together as one pipeline, rather than
three parts that each work on their own. Most of it does. The verification also
turned up a real defect on the extension-to-analysis path, so this records both.

## The integration, as designed

Three arrows:

1. **platform design to extension.** A study compiles into a machine-readable
   capture configuration. The participant gets a one-use pairing link; the extension
   redeems it (`POST /pair/redeem`), which consumes the link and returns the capture
   config, a session credential, and the ingest endpoint. The extension then shows the
   returned consent statement and only persists and applies those values after the
   participant accepts.
2. **extension to platform.** The extension mirrors captured events to
   `/ingest/events` with the bearer credential (its `HttpSink`).
3. **platform complements the data.** Events join into one timeline, export as JSON
   and CSV, and feed the per-RQ report and paper draft.

Privacy guarantee: capture is sizes, shapes, and timings, not raw code, keystrokes,
or clipboard text.

## How I tested it

Middleware served locally against SQLite with the pilot protocol loaded, frontend
built so the UI serves:

```bash
export MIDDLEWARE_DB=.study-data/mw-verify.sqlite3
export MIDDLEWARE_PROTOCOL=protocol/examples/pilot-study.yaml

(cd platform && npm install && npm run build)   # build the SPA so / serves
uv run python -m middleware serve &             # background it; smoke runs from root
server=$!; trap 'kill "$server" 2>/dev/null' EXIT

SMOKE_NO_COMPOSE=1 bash scripts/smoke.sh        # SMOKE OK
```

Alongside the smoke run I exercised the pieces directly, and compared what the real
extension emits against what the analysis consumes, because a passing smoke run does
not prove those two agree.

## What holds up

**Pairing works and enforces consent and privacy.** Minting a one-use token,
redeeming it, and receiving identity, capture config, credential, and ingest
endpoint are all covered. Minting refuses before the ethics gate, single-use links
reject reuse, revoked links reject, capture config is credential-gated, and the
content policy returns `metadata-only`, so the privacy guarantee is enforced rather
than assumed. The extension's redeem contract (`extension/src/vscode/pairing.ts`)
matches the platform response (`middleware/src/middleware/app.py`) field for field.

**The extension works.** Its own suite passes all 141 tests on Node 26, including
the `HttpSink` mirror behaviour and the crash-recovery seq handling the platform's
gap detection relies on.

**The platform internals are sound.** Ingest is idempotent, with the dedupe enforced
at the database level on `(session_id, source, seq)`. Sequence gaps are reported
rather than swallowed. Events join into one time-ordered dataset with the join keys
intact, export as JSON and CSV, and the per-RQ report and paper draft generate.

Test results on this codebase: protocol 57, the middleware compiler, conversation,
enrollment, and pairing suites 96 combined, extension 141. The smoke run is fully
green: all ten analysis recipes produce results.

## What does not hold up

The smoke run being fully green is itself the warning. It drives ingest with
`middleware/scripts/replay_session.py` and synthetic fixtures whose event-type names
match what the analysis expects. The real extension has moved on, and its vocabulary
no longer matches. I found this by diffing the type strings the extension emits
against the type strings every recipe consumes.

**Confirmed bug: the debrief survey never reaches its analysis.** The extension emits
`end_survey_response` and `end_survey_skipped`
(`extension/src/vscode/extension.ts:617,619`). The debrief recipe requires
`end_survey` and reads `of_type("end_survey")`
(`analysis/src/analysis/recipes/tlx_debrief.py:28,32`). `of_type` filters with pandas
`.isin()` (`analysis/src/analysis/dataset.py:120`), an exact match, and nothing
renames the type in between, so real extension data yields zero debrief rows and the
TLX / cognitive-load measure silently gets nothing. On a dataset holding a real
`end_survey_response` event, the recipe's `of_type("end_survey")` returns 0 rows,
while `of_type("end_survey_response")` returns 1. The `tlx-debrief` recipe still shows
green in the smoke run only because the fixtures use the old `end_survey` name.

The name is not the only drift. The real payload is nested,
`{responses, comments, msToComplete}` (`extension/src/vscode/endSurvey.ts:4`), whereas
the fixtures carry flat numeric fields (`{mentalDemand, effort, frustration}`). The
recipe treats every numeric column as a TLX subscale
(`analysis/src/analysis/recipes/tlx_debrief.py:34`), so on real data it would miss the
nested `responses.*` ratings and wrongly count `msToComplete` as a subscale. Fixing
the event name alone does not close the loop. Tracked as a separate bug.

**Stale fixtures.** The sample data is schema v2/v3; the extension is at v4
(`extension/src/core/types.ts:22`) and uses the newer names. No v4 event traverses
`/ingest/events` in any test, which is what let the drift hide. The fixtures should
be regenerated from the real extension.

**A measure with no consumer.** The extension emits `comprehension_probe_response`,
but no recipe consumes it. Either an intentional collect-for-context choice or a
quieter version of the same drift. Worth a decision, lower priority.

## Fresh-checkout gotchas

Running `python -m middleware serve` returns 404 at `/` until `platform/dist/`
exists, since the SPA is a build artifact (git ignored). `npm run build` creates it,
and so does `docker compose up --build`, which the smoke test does by default. The
smoke run also expects the pilot protocol loaded and `srs.md` shipped so
`/requirements` resolves. Setup steps, not code changes, but worth a line in the
README.

## A note on method

The pairing and platform tests run against the real application in process (FastAPI
TestClient), the same code path a socket would hit but not a literal network run.
Untested over a real socket: CORS, the SPA static mount under real headers, and the
`base_url` used to build the returned `ingestEndpoint`, which behind a proxy could
hand the extension a wrong endpoint. None are implicated in the bug above.

## Verdict

Partially verified, with one real defect found. The pairing handoff, the consent and
privacy model, the extension itself, and the platform's ingest and analysis internals
are all solid and covered. What is not yet true is that the real extension's output
flows correctly into the analysis: the `end_survey` name drift is a live break in the
debrief measure, and the stale fixtures were masking it well enough that the smoke run
stays green. For a verify task that is the right outcome. Closing the round trip takes
more than renaming the event: the recipe also has to unwrap the real nested payload
(read `responses.*`, exclude `msToComplete`) rather than treat every numeric column as
a subscale, and the fixtures need regenerating to the real v4 shape.

---
*Verified by @1122Louis, 2026-10-01, against origin/main, branch
`verify-the-integration-of-tern-extension-with-platform-64`*
