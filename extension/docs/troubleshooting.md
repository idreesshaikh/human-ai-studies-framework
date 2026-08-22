# Troubleshooting

TERN is built to never interrupt the participant, which means most failures
are quiet: nothing pops up, the session just doesn't capture what you
expected. So the habit that saves you is checking early rather than waiting
for the end of a session to find that one of your data streams captured
nothing.

Two facts make troubleshooting straightforward once you internalise them:

- **The JSONL file is the source of truth.** Every event is written to
  `<workspace>/.study-data/<participant>_<timestamp>.jsonl` before anything
  else happens. If an event is in that file, it was captured. Open it first.
- **The middleware is only a mirror.** Streaming to the middleware is
  best-effort. If it's down or misconfigured you lose the live view, not the
  data  -  the file still has everything.

## First checks

When something looks wrong, run through these before digging in:

1. Is a session actually running? The status bar shows a countdown while a
   session is active; if it says `Study: idle`, nothing is being captured.
2. Open the data folder (_TERN: Open Study Data Folder_) and check the JSONL
   file is there and growing.
3. Are you working in a captured language? By default the behavioral capture
   only watches Python (`tern.behavior.languages`). Editing a Markdown or JSON
   file records almost nothing  -  this is the single most common surprise.
4. Is the file inside the workspace? Files outside the open workspace folder
   are ignored (`tern.behavior.workspaceInternalOnly`).

## Nothing is being captured at all

Almost always one of the first checks above.

- **No session running.** Start one with _TERN: Start Study Session_.
- **Wrong language.** The pilot config captures Python only. If the
  participant is working in another language, either that's expected (the
  study is Python-only) or you need to add the language to
  `tern.behavior.languages` *and* `tern.stuck.languages`.
- **File outside the workspace.** Open the task folder as the workspace so
  its files are counted as internal.
- **Behavioral capture switched off.** `tern.behavior.enabled` is the master
  switch; if it's `false`, none of the behavioral streams run.

If the JSONL file has `session_start` but nothing after it, capture is
running but filtered out  -  check the language and workspace scope. If the
file doesn't exist at all, the session didn't start or the output directory
isn't writable (`tern.output.directory`).

## Data isn't reaching the middleware

First: confirm the data is in the JSONL file. If it is, you haven't lost
anything  -  this is a mirroring problem, not a capture problem.

- **No endpoint set.** Streaming is off unless `tern.output.httpEndpoint` is
  set (e.g. `http://127.0.0.1:8000/ingest/events`). An empty value means
  file-only.
- **Middleware not running / wrong URL.** The extension will not complain
  loudly  -  it retries quietly and keeps the events buffered. Check the
  middleware is up and the URL is exactly right, including the
  `/ingest/events` path.
- **Paired session, stale endpoint.** When a participant connects to a study,
  the endpoint comes from the study, not from local settings. If it's wrong,
  it's wrong in the protocol, not in VS Code.
- **The buffer is capped.** If the middleware stays unreachable for a long
  time the extension keeps the most recent events and drops the oldest ones
  from the *send* buffer  -  but those older events are already safe in the
  JSONL file, so re-ingesting the file after the fact recovers them.

The batches are sent every few seconds as
`{"source":"cognitive-overlay","events":[...]}`. If you're inspecting the
middleware, that's the shape to expect.

## The stuck prompt never appears

The stuck detector is deliberately conservative  -  it would rather miss a
stuck moment than nag someone who's fine. Reasons it stays quiet:

- **The participant isn't visibly active.** Without eye tracking, motionless
  reading is indistinguishable from being away, so the detector needs faint
  activity  -  a cursor move, a scroll, focus on the window. Perfectly still
  means idle, not stuck, and nothing fires.
- **The threshold hasn't elapsed.** It waits for `tern.stuck.thresholdSeconds`
  (default 90) of dwelling on the same region with no edits. Any edit resets
  that clock.
- **Cooldown.** After a prompt (any prompt), stuck detection pauses for
  `tern.stuck.cooldownMinutes` (default 5).
- **Wrong language.** `tern.stuck.languages` restricts detection; if it's set
  to `["python"]` and the participant is elsewhere, it won't fire.
- **The window is unfocused, or another prompt is showing.** Detection is
  suppressed in both cases.

To see it quickly while testing, set `tern.stuck.thresholdSeconds` to `15`
and `tern.stuck.cooldownMinutes` to `1`, then leave the cursor in a captured
file and nudge it occasionally without typing.

## The fatigue prompt never appears

- **It's waiting for a pause.** A scheduled probe holds until the participant
  stops typing for `tern.fatigue.waitForPauseSeconds` (default 4). It gives
  up and shows anyway after 60 seconds, so a genuinely non-stop typist still
  gets sampled  -  but a steady typist can push each probe a little later than
  the nominal interval.
- **You're in the quiet tail.** No probes appear in the final
  `tern.fatigue.quietTailMinutes` of the session.
- **The interval plus jitter hasn't come round yet.** Probes are spaced by
  `tern.fatigue.intervalMinutes` randomised by `tern.fatigue.jitterPercent`,
  so the exact timing moves session to session by design.

To trigger one on demand, run _TERN: Log Fatigue Now_.

## Some events are missing / sequence numbers have gaps

This is expected and, importantly, *detectable* rather than hidden. Every
event carries a per-session `seq` that increments by one. A gap in `seq`
means an event didn't make it  -  the design guarantees you can see the loss
even where it couldn't be prevented, so you can decide how to treat that
session.

- Gaps in the **middleware** view but not the JSONL file mean the mirror
  dropped a batch; the file is complete. Re-ingest the file.
- Gaps in the **JSONL file** itself are rare and point at a disk/write
  problem (a full or read-only output directory).

## The session timer looks wrong after a break or a sleep

The study clock is wall-clock based and excludes paused time, so a few
things that look like bugs are intended:

- **A laptop that slept does not stretch the session.** Elapsed time is real
  elapsed time; the clock doesn't run forward during sleep in a way that adds
  fake work time.
- **Paused time is excluded.** If you used pause/resume for a break, that
  gap is kept out of both the clock and the probe schedule  -  the remaining
  time is shorter than the wall-clock gap suggests, on purpose.
- **After a crash or reload**, the extension offers to recover the
  interrupted session on next launch, and counts the downtime as paused time
  rather than work.

## I couldn't connect to a study

The pairing step (_TERN: Connect to Study_) can refuse for a few specific
reasons:

- **"No protocol for this study."** Pairing is blocked until the study has a
  compiled, validated protocol  -  ask the researcher to finish and apply the
  design conversation's draft. This is a study-state issue, not a client
  problem; there is no separate ethics-approval gate to clear.
- **The link is invalid, used, or expired.** A single-use link that's already
  been redeemed, or one past its expiry, won't work  -  ask the researcher for
  a fresh connection string.
- **"That does not look like a connection string."** Paste the whole line,
  including the `#` and the token after it (`https://server#token`).
- **Can't reach the server.** The middleware URL in the connection string
  isn't reachable from the participant's machine  -  check the address and the
  network.

## Edit origins look wrong (human / AI / paste mislabeled)

The origin of an edit burst is a best-effort classification, and it has known
blind spots  -  an AI tool that streams its output character by character can
evade the size heuristic, and a paste made through the context menu rather
than the keyboard may not be seen as a paste. These limits are documented in
[`adaptation-notes.md`](adaptation-notes.md); if origin accuracy matters for
your analysis, read that first so you know what the numbers can and can't
tell you.

## Still stuck

If a problem isn't covered here, the JSONL file plus the browser view of the
middleware (`/sessions/{sessionId}/events` and `/sessions/{sessionId}/gaps`)
together show exactly what was and wasn't captured, which is usually enough
to tell a capture problem from a mirroring problem. For how the pieces fit
together, see [`PROJECT_GUIDE.md`](../PROJECT_GUIDE.md).
