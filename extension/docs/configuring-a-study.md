# Configuring the extension for a study

This is the guide for whoever sets up a study and has to decide what TERN
captures and how it behaves. It assumes you already know what the extension
is (see the [README](../README.md)); the goal here is to make the settings
make sense, so you can tune them for your study instead of guessing.

The one thing to keep in mind: **every setting can come from the study
protocol**. When a participant connects to a study, their identity,
condition, and capture settings are derived from the protocol and pushed to
the IDE automatically — nothing is configured by hand in the field. The
settings below are what those derived values map onto, and what you edit
directly when you're testing locally or overriding a default.

## Where settings come from

There are two ways a setting gets its value, and they don't fight:

- **From the protocol (enrollment).** The researcher generates a connection
  string; the participant runs _TERN: Connect to Study_ and the settings
  arrive with it. This is how real sessions run. See the README's
  "Connecting to a study" section.
- **By hand (local testing).** You open VS Code settings and set `tern.*`
  keys yourself, or paste a settings block into `.vscode/settings.json`.
  Useful when you're trying things out without a middleware in the loop.

You can also derive a settings block straight from a protocol without pairing:

```bash
uv run protocol derive overlay-settings protocol/examples/pilot-study.yaml \
    --participant P07 --condition ai-assisted
```

That prints the exact `tern.*` JSON the protocol implies. Paste it into the
workspace's `.vscode/settings.json` and you have a faithful local copy of a
real session's configuration.

## The session itself

| Setting | Default | What it decides |
| --- | --- | --- |
| `tern.participantId` | `""` | The participant this IDE records as. Can be set when you start a session, so leaving it blank is fine. |
| `tern.condition` | `unspecified` | The study arm: `ai-assisted` or `unassisted`. This is on every event row — get it right. |
| `tern.session.durationMinutes` | `60` | Session length. When the clock runs out the end-of-study survey opens on its own. |

The clock is wall-clock based and survives a laptop sleeping or the window
reloading, so a 45-minute session is 45 minutes of real work, not 45 minutes
that a closed lid quietly stretched. Breaks can be paused and resumed, and
paused time is kept out of the study clock.

## Fatigue probes

TERN samples fatigue with a short Likert prompt during the session. Four
settings shape when it appears.

| Setting | Default | What it decides |
| --- | --- | --- |
| `tern.fatigue.intervalMinutes` | `15` | Roughly how often a probe appears. |
| `tern.fatigue.jitterPercent` | `20` | Randomizes each interval by ±this percent. |
| `tern.fatigue.waitForPauseSeconds` | `4` | Hold the probe until the participant stops typing for this long. |
| `tern.fatigue.quietTailMinutes` | `5` | Stop probing in the last few minutes before the debrief. |

The jitter is deliberate, not cosmetic. A probe that lands on a fixed
15-minute clock is one participants learn to expect, and anticipated probes
change behavior — a known problem with experience sampling. The random
offset breaks the pattern. Set `jitterPercent` to `0` only if you have a
reason to want strictly periodic sampling.

`waitForPauseSeconds` is what keeps the probe from interrupting a keystroke.
It waits for a real pause; if the participant never pauses it gives up after
60 seconds and shows anyway, so a very busy session still gets sampled.

## Stuck detection

TERN watches for two patterns that suggest the participant is stuck —
dwelling on the same lines without editing while still active, or scrolling
back and forth over the same region — and draws a soft prompt around the
code when it sees one.

| Setting | Default | What it decides |
| --- | --- | --- |
| `tern.stuck.enabled` | `true` | Turn stuck detection on or off. |
| `tern.stuck.thresholdSeconds` | `90` | Dwell time on one region, no edits, before prompting. |
| `tern.stuck.cooldownMinutes` | `5` | Minimum gap between two stuck prompts. |
| `tern.stuck.languages` | `[]` (all) | Restrict detection to certain languages, e.g. `["python"]`. |

If you're demonstrating the feature and don't want to wait, drop
`thresholdSeconds` to `15` and `cooldownMinutes` to `1`, start a session,
and leave the cursor in a file without typing.

One thing worth understanding: the detector requires the participant to be
*visibly active* before it calls anything stuck. Without eye tracking there
is no way to tell someone reading intently from someone who walked away, so
faint activity — a cursor move, a scroll, focus on the window — has to be
present. No activity means idle, not stuck.

## What the behavioral leg captures

`tern.behavior.enabled` (default `true`) is the master switch for the second
leg — the one that records how the participant works rather than what they
say. Under it, each stream can be turned off independently:

| Setting | Records |
| --- | --- |
| `tern.behavior.captureFocus` | Editor/tab focus switches and window focus. |
| `tern.behavior.captureVisibleRanges` | Debounced scroll position, for coverage analysis. |
| `tern.behavior.captureEditBursts` | Aggregated edits with an origin guess (human / AI / paste / undo-redo). |
| `tern.behavior.captureClipboard` | Paste sizes and internal-copy timing. |
| `tern.behavior.captureAiLifecycle` | AI suggestion shown/accepted/rejected, with review latency. |
| `tern.behavior.captureSaves` | File save sizes. |
| `tern.behavior.captureHeartbeat` | Active/idle transitions. |
| `tern.behavior.captureAttention` | Region-level time-on-code from caret and hover. |

Two settings scope all of this:

- `tern.behavior.languages` (default `["python"]`) — only files in these
  languages are captured. The pilot is Python-only; widen it when your study
  does.
- `tern.behavior.workspaceInternalOnly` (default `true`) — files outside the
  workspace are never captured, only noted as `external` in focus events.

None of these streams record content. They record sizes, line counts,
timings, and salted hashes — never code text, keystrokes, or clipboard text.
That is a property of the instrument, not a setting you can accidentally turn
off, and it's covered in more detail under [Privacy](#privacy) below.

## Recording provenance

Three settings record what the session ran against, so a result can be
reproduced later. They don't change behavior; they land in the environment
snapshot at session start.

| Setting | Example | Why it's there |
| --- | --- | --- |
| `tern.session.taskId` | `maintenance-A` | Which task the participant worked on. |
| `tern.session.agentTool` | `claude-code` | The AI tool used in the ai-assisted arm. |
| `tern.session.agentModelId` | `claude-fable-5` | The exact model behind that tool. |

If you skip these, the data is still valid — you just lose the ability to say
precisely which tool and model a session used, which matters when you write
the study up.

## The tuning knobs you usually leave alone

The `tern.behavior.*` timing settings — `burstGapMs`, `aiCorrelationMs`,
`aiBlockCharThreshold`, `aiBlockMaxDurationMs`, `pasteCorrelationMs`,
`idleWindowSeconds`, the debounce and attention-radius values — control the
internals of the classifiers. The defaults are deliberate and hold across
studies, so treat these as advanced.

The two worth knowing about, because they decide how an edit gets labeled
`ai`:

- `aiBlockCharThreshold` (default `80`) and `aiBlockMaxDurationMs`
  (default `50`) are the "nobody types 80 characters in 50 milliseconds"
  rule. A block that large arriving that fast is treated as injected code,
  not typing.
- `aiCorrelationMs` (default `500`) and `pasteCorrelationMs` (default `100`)
  are the windows for tying an edit to an accepted AI suggestion or a paste.

If your study uses an AI tool that streams its output character by character
rather than dropping it in as a block, the size heuristic won't catch it —
you'll be relying on the accept-correlation instead. That's a real blind
spot, documented alongside the others in
[`adaptation-notes.md`](adaptation-notes.md).

## Where the data goes

| Setting | Default | What it decides |
| --- | --- | --- |
| `tern.output.directory` | `""` → `<workspace>/.study-data` | The folder for the JSONL session files. |
| `tern.output.httpEndpoint` | `""` (off) | A middleware endpoint to mirror events to, e.g. `http://127.0.0.1:8000/ingest/events`. |
| `tern.studyId` | `""` | The study this IDE is paired to. Set for you when you connect; you don't edit it by hand. |

The JSONL file is always the source of truth. If you set an HTTP endpoint,
events are also batched to the middleware every few seconds, but that is
best-effort mirroring — a middleware that's down or slow never blocks the
session and never loses data, because the file already has it. Missing
events show up as gaps in the sequence numbers, so loss is always
detectable even when it can't be prevented.

## A worked example: the pilot

The pilot study is a within-subjects comparison on Python maintenance tasks,
45 minutes a session. Derived from its protocol, the configuration comes out
close to this:

```jsonc
{
  "tern.participantId": "P07",
  "tern.condition": "ai-assisted",
  "tern.session.durationMinutes": 45,
  "tern.fatigue.intervalMinutes": 15,
  "tern.fatigue.jitterPercent": 20,
  "tern.stuck.enabled": true,
  "tern.stuck.thresholdSeconds": 90,
  "tern.stuck.languages": ["python"],
  "tern.behavior.languages": ["python"],
  "tern.output.httpEndpoint": "http://127.0.0.1:8000/ingest/events"
}
```

Everything else stays at its default. For the other arm, the only change is
`tern.condition` to `unassisted`.

## Privacy

The instruments capture aggregates, shapes, timings, and salted hashes.
They do not capture code content, keystrokes, or clipboard text. Two narrow
exceptions exist for the agent leg — the content of an AI conversation and
workspace snapshots — and both are governed by the protocol's content
policy, so they only ever happen when a study has consented to them
explicitly.

This is worth stating plainly to participants, and the enrollment flow does:
before any session starts, the consent screen names exactly which
instruments are on. Turning individual `capture*` streams off narrows what's
collected further, but nothing you leave on will record the text of what the
participant wrote.
