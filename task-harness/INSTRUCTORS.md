# Instructor notes (delete this file and `solution/` before publishing the template)

## Fidelity to Peng et al. (2023), arXiv:2302.06590

| Element | Source |
|---|---|
| Task text at the top of `index.js` | **Verbatim** from Figure 4 of the paper |
| Test suite of twelve checks, visible to participants but not editable | Paper describes it; the tests themselves are **not published**, so ours are a reconstruction |
| `content/` files | Not published; ours are reconstructions |
| Function signatures and `// YOUR CODE HERE` in `index.js` | **Deliberate adaptation.** The paper recruited professional freelancers who code daily; our participants are students new to coding, so the skeleton gives them structure. The paper's skeleton had only the task comment |
| Timing: start to first test run that passes all tests | **Adapted.** The paper used GitHub Classroom timestamps (repo creation to first passing push). We use local timestamps from `scripts/study.js` (`npm run begin`, then each `npm test` run) |
| Conditions: Copilot (plus a 1-minute intro video) vs. no Copilot; otherwise unconstrained (search, Stack Overflow allowed) | As in the paper |

Because the original tests are unknown, absolute times are not directly comparable to the paper's (71 min treated and 161 min control). Pilot the tests, and report both deviations (reconstructed tests, scaffolded skeleton). The student population also differs from the paper's freelancers, so treat this as a conceptual replication in a new population and compare the direction and size of the effect, not absolute times.

## Setup (local)
1. Verify: temporarily replace `index.js` with `solution/index.js` (change `'..', 'content'` to `'content'`), run `npm test`, expect 12 passing, then restore.
2. Delete `INSTRUCTORS.md` and `solution/`, then zip or share the folder (a private repo works too). Do not include `.study/`.
3. Randomize participants into the two conditions yourself, and tell each one whether to use Copilot. Nothing enforces this, so ask for confirmation in an exit survey.
4. Participants run `npm run begin -- <id>` when ready, then `npm test` as they work. `.study/start.json` holds the start time and `.study/runs.jsonl` one line per test run (`at`, `passed`, `total`).
5. Completion time = `startedAt` to the first `runs.jsonl` entry with `passed == total == 12`. Runs with fewer passes show partial progress for non-finishers.

## Limits of the local setup
- Timestamps are self-reported by the participant's machine and can be edited or reset. Use a supervised session, or collect the folder right after the session.
- Participants can edit `test/` locally. Check `test/` against the original (for example by hash) when you collect results, or run the original tests on their `index.js` yourself.
- Not in the paper's setup, but possible here: run sessions in the lab, so start and end are observed directly.
