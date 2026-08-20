# TERN · Developer Study Companion

TERN is the VS Code extension participants run during a study. It hosts two of
the framework's instrument legs — the **cognitive/self-report** leg and the
**behavioural telemetry** leg — under one install and one sink pipeline. It is
configured entirely by the protocol you designed, so the study you designed is
the study that runs.

<figure markdown="span">
  ![TERN sidebar, idle](assets/screens/tern-sidebar-idle.png){ width="700" }
  <figcaption>The TERN sidebar: session status, what is captured, and where your data goes.</figcaption>
</figure>

## What TERN does

- **Runs the study session clock** — start a session with a participant ID and
  an A/B condition; a status-bar countdown is the only permanent UI. When time
  is up, a frosted-glass end-of-study debrief (NASA-TLX-inspired, 7-point
  scale) opens automatically.
- **Samples fatigue in flow** — a 7-point Likert micro-prompt appears at a
  configurable interval as a native floating QuickPick. It waits for a typing
  pause, so it never interrupts mid-keystroke.
- **Detects stuck moments** — when a participant dwells on the same code region
  without editing, or scroll-thrashes re-reading the same area, a soft
  rectangular border is drawn around those lines with clickable actions:
  *Yes, I'm stuck · No, just thinking · I'd like a hint · Dismiss*.
- **Records everything as research-ready JSONL** — one file per session,
  optionally mirrored to the team's Python middleware over HTTP.
- **Pairs with the platform** — participant links (`vscode://…/pair` deep
  links) install the study already configured as designed: consent statement,
  capture config, everything.

## The four angles

| Leg | Instrument | What it captures |
| --- | --- | --- |
| How participants feel | TERN probes | Fatigue Likert, end-of-session TLX survey |
| What participants do | TERN telemetry | Focus switches, edit bursts, pastes (sizes only), stuck episodes |
| What the AI does | agent-capture | Tool calls, transcripts, suggestion lifecycle |
| What the code looks like | metrics | Complexity profile of the code produced |

## Design principles

- **Zero distraction.** The countdown in the status bar is the only permanent
  UI. Prompts defer to flow — fatigue prompts wait for ≥4 s of typing silence,
  stuck prompts never steal focus and time out silently after 60 s.
- **One prompt at a time, everywhere.** Any visible prompt suppresses stuck
  detection, and every prompt interaction resets the detector cooldown.
- **FR-ETH-2-safe by construction.** Capture is sizes, shapes, and timings
  only — never code content, keystrokes, clipboard text, or off-workspace
  paths.

## Section contents

- [Install](install.md) — install the extension and pair it with a study.
- [Using TERN](using.md) — sessions, fatigue probes, stuck detection, and the
  debrief.
- [Captured data](captured-data.md) — the event schema, one file per session.
- [Privacy](privacy.md) — what is captured, what never is, and where data
  goes.