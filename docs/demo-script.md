# Demo screencast script

A five-minute video for a tool/demo track. The mechanics of each step are in
the [rehearsal guide](demo-runbook.md); this is the narrative, the timing, and
what must be visible on screen.

## Before recording

- Seed a clean rehearsal database (`backup-seed`, see the rehearsal guide) so
  no earlier state is visible.
- Set the editor and browser to a light theme at 1920×1080, font size up.
- Close every unrelated tab, notification, and panel. A reviewer watching at
  1.5× cannot afford visual noise.
- Have the failing case ready in a second window — you will not have time to
  induce it live.
- Say nothing that the screen does not show. Demo reviewers discount narration
  they cannot verify.

## The spine

One claim, demonstrated three times: **the protocol is the single source, so
the pieces cannot disagree.** Everything on screen should serve that.

---

### 0:00–0:30 — The problem

Show a whiteboard-style slide, not the app: a study design, an editor logger,
and an analysis script drawn as three separate boxes.

> "A developer study needs a protocol, instrumentation, and analysis. Assembled
> separately, they can disagree. A measure the design promises never gets
> recorded — and you find out at analysis time, when the sessions are over."

Do not linger. The problem statement is the setup, not the demo.

### 0:30–1:30 — Design, from a question

In the web workspace, start a study from the template registry. Show the
research questions, conditions, and the analysis plan side by side.

> "One protocol holds the questions, the conditions, the measures, and the
> analysis plan."

Approve the protocol. Show the version stamp.

**On screen:** the protocol YAML, briefly. Reviewers want to see the artifact
is real and readable, not a black box.

### 1:30–2:15 — The mismatch is refused

This is the money shot. Add a recipe to the analysis plan whose required event
the protocol does not capture, and run validation.

> "This analysis needs suggestion events. The protocol doesn't capture them.
> The planner refuses the plan and names the missing event type — now, while
> the study can still be fixed, not after data collection."

Let the error message sit on screen for a full three seconds. Then fix the
capture scope and show it pass.

If the video only lands one thing, land this.

### 2:15–3:15 — Capture in the developer's own editor

Mint a participant link. Switch to VS Code, connect TERN, and walk the consent
and capture pre-flight.

> "The participant sees exactly what will be recorded before anything is."

Start a session. Edit and save a file, switch focus, log a fatigue probe.

> "TERN records edit sizes, focus changes, and timings. It does not record
> source text, keystrokes, or the clipboard."

**On screen:** the capture pre-flight listing. This is the consent story, and
reviewers of human-subjects tooling look for it specifically.

### 3:15–4:15 — Export and analyse

End the session, run the debrief, export the dataset. Drop to the terminal:

```bash
uv run analysis run study.yaml --dataset dataset.json
```

Open the generated `report.md`. Scroll to a recipe section showing the test,
the effect size, the per-cell n, and the small-n caveat.

> "Every section names the research question it answers, and every statistic
> reports its own n."

### 4:15–4:45 — What the numbers are not

Stay on the report and scroll to the top so the banner is unmissable.

> "This run used synthetic dry-run rows, so the report says so on its own face.
> Figures are watermarked. Mix synthetic and participant rows and the run exits
> non-zero. The pipeline connects — that is all this output claims."

Do not rush this. A demo audience that has seen a hundred tools will remember
the one that told them what its own output was worth.

### 4:45–5:00 — Close

> "No study has been run with PHOENIX yet. The mechanism works end to end; the
> next step is the first real study. It's MIT licensed and the artifact runs
> offline with no credentials."

End on the repository URL.

## What to leave out

- The literature corpus and paper search. Interesting, not the claim.
- The design conversation with a model. It needs an API key, it is optional,
  and showing an LLM proposing a study design invites the wrong question in a
  five-minute video.
- Architecture diagrams. The reviewers read the paper for that.
- Any statistic presented as a finding.

## Rehearsal checklist

- [ ] Full run-through under 5:00 without cuts
- [ ] Validation-failure message legible at 720p
- [ ] Consent pre-flight legible at 720p
- [ ] Synthetic banner visible in the final scroll
- [ ] No participant link, token, or `.env` value on screen at any point
- [ ] No personal file paths, browser bookmarks, or notifications visible
- [ ] Audio levelled; no dead air over the terminal steps
