# Privacy

TERN is built to a hard rule — **FR-ETH-2-safe by construction**: capture is
sizes, shapes, and timings only. Never code content, keystrokes, clipboard
text, or off-workspace paths.

## What is captured

- What you **did**: focus switches between files, edit bursts (characters
  added/deleted, lines touched — not the text), paste sizes (not paste
  content), save events, active/idle heartbeats, scroll coverage.
- How you **felt**: fatigue Likert answers (1–7) and the end-of-session
  debrief responses.
- What the **AI did**: inline-suggestion lifecycle — shown, accepted,
  rejected, dismissed — with review latency, and the agent tool/model
  environment.
- Where you got **stuck**: a line-region band with the reason (dwell /
  scroll-thrash), plus your answer to the stuck prompt.

## What is never captured

- ❌ Keystrokes and raw code content — edit bursts carry counts and origins
  only.
- ❌ Clipboard text — only `charCount` and `lineCount` of a paste.
- ❌ Off-workspace paths — capture is filtered to workspace-internal files and
  protocol-declared languages.
- ❌ Diagnostic text — `ide_health` carries counts, never error messages.

## Where data goes

1. **Locally first** — one JSONL file per session in
   `<workspace>/.study-data/`. The file is always written, even when the
   network is down.
2. **Optionally mirrored** — if the study protocol sets
   `tern.output.httpEndpoint`, batches POST to the study's middleware every
   5 s. Batched events join the same stream as the platform's other
   instrument legs.

## Consent and disclosure

The capture config is part of the protocol — approved by the researcher and
disclosed in the participant's **consent statement** before anything runs. A
capture config the researcher has not approved never runs. The preflight
summary shown at session start states exactly what will be captured and where
it will go; the session begins only after you confirm.

## Crash recovery

An interrupted session (IDE crash, window reload) is offered for **crash
recovery** on next launch, with the downtime counted as paused time rather
than work — no event is lost, and no event is fabricated.