# Instructor notes (delete this file and `solution/` before publishing the template)

## Fidelity to Peng et al. (2023), arXiv:2302.06590

| Element | Source |
|---|---|
| Task text at the top of `index.js` | **Verbatim** from Figure 4 of the paper |
| Test suite of twelve checks, visible to participants but not editable | Paper describes it; the tests themselves are **not published**, so ours are a reconstruction |
| `content/` files | Not published; ours are reconstructions |
| Function signatures and `// YOUR CODE HERE` in `index.js` | **Deliberate adaptation.** The paper recruited professional freelancers who code daily; our participants are students new to coding, so the skeleton gives them structure. The paper's skeleton had only the task comment |
| Timing: start to first test run that passes all tests | **Adapted.** The paper used GitHub Classroom timestamps (repo creation to first passing push). We use TERN's session clock (`session_start`) and a `task_outcome` event per `npm test` run from `scripts/study.js` |
| Conditions: Copilot (plus a 1-minute intro video) vs. no Copilot; otherwise unconstrained (search, Stack Overflow allowed) | As in the paper |

Because the original tests are unknown, absolute times are not directly comparable to the paper's (71 min treated and 161 min control). Pilot the tests, and report both deviations (reconstructed tests, scaffolded skeleton). The student population also differs from the paper's freelancers, so treat this as a conceptual replication in a new population and compare the direction and size of the effect, not absolute times.

## Setup (TERN)
1. Verify: temporarily replace `index.js` with `solution/index.js` (change `'..', 'content'` to `'content'`), run `npm test`, expect 12 passing, then restore.
2. Delete `INSTRUCTORS.md` and `solution/`, then zip the folder. Do not include `.study-data/`.
3. In the platform, create the study and set this zip as the **Study folder** (see the participant-links docs). TERN downloads it, unpacks it and opens it for each participant. Declare `task-harness` as the producer and instrument for the task outcome measure.
4. Randomization and the condition come from the study server. Nothing enforces Copilot on or off: tell participants, and ask in the exit survey.
5. Participants connect to the study in VS Code, start the session and run `npm test` as they work. Each run appends one `task_outcome` event to `.study-data/task-harness.jsonl` (`passed`, `passedTests`, `totalTests`, and `firstGreenMs` on the first all-green run). The event copies session, participant and condition from TERN's own `session_start`. If no session is running, `npm test` warns and logs nothing.
6. After the session, post the events to the middleware. Run `npm run export` in the participant's folder and POST the output to `/ingest/events`. Re-posting is safe: events are deduplicated by session, source and sequence.
7. Analysis: the `task-outcome-by-condition` recipe reads these events for pass rates and time to first green.

## Limits
- **Credentials:** TERN keeps the session credential in VS Code SecretStorage, so the harness cannot post events itself. The harness events are therefore posted by you afterwards, without the participant's credential. In a test against a middleware with no registered study the three events were accepted but flagged (probably the missing credential). Check how your study's server flags them before relying on them.
- **Breaks:** `firstGreenMs` is plain `ts` minus `session_start`, so it includes paused breaks. TERN's own clock excludes them; compute from TERN's events if breaks matter.
- **Local edits:** participants can still edit `test/` or the logged files locally. Collect the folder right after the session, check `test/` against the original by hash, or rerun the original tests on their `index.js`.
