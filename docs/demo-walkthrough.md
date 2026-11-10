# Seven-minute StudyLoop showcase

## Prepare

Install dependencies and build the platform as described in
[demo readiness](demo-readiness.md), then run:

```bash
uv run --no-sync python scripts/run_demo.py
```

Open `http://127.0.0.1:8000`. The launcher uses temporary storage, disables
provider calls and starts a fresh example on every run. Nothing entered here
is retained after stopping the launcher. Close unrelated tabs and notifications.
Rehearse at the actual presentation resolution and confirm downloaded files
open. For an occupied port, add `--port 8001` and use that address.

## Tell one story

The researcher is preparing a comparison of bug fixing with and without
Copilot. The outcomes are time to first passing test and reported workload.
The tool makes the choices, capture configuration, session integrity and export
inspectable. It does not establish that these outcomes represent every aspect
of productivity or that the analysis assumptions fit a real population.

| Time | Action | Point to explain |
| --- | --- | --- |
| 0:00–0:30 | Introduce the study question | A researcher must carry the same intended method through setup, capture and analysis |
| 0:30–1:30 | Create a separate blank study; open manual protocol entry | Chat, checklist and templates feed the same reviewable protocol; use the checklist in this offline rehearsal |
| 1:30–2:30 | Enter the example details below; review and apply | The researcher approves consequential decisions; the compiler checks supported structure and contracts |
| 2:30–3:15 | Open Plan | Recruitment calculations depend on declared assumptions; a calculated number is not a justification for them |
| 3:15–4:00 | Open the seeded example and its Run tab | Illustrative participant links expose assignment and capture scope; they cannot pair a real editor |
| 4:00–5:30 | Open Data in the seeded example | Show the synthetic label, one incomplete session, a sequence gap and control-arm signals; missing evidence remains visible |
| 5:30–6:30 | Download a data bundle and design card | The study record is portable; default data exports exclude the simulated observations |
| 6:30–7:00 | State the boundary and close | The artifact supports a workflow; interviews explain researcher needs; software tests establish tested behavior |

Manual entry values, adapted to the labels in the form:

- Title: `Copilot and Java bug fixing`
- Question: `Does Copilot change time to the first passing test on Java bug fixes?`
- Design: within subjects; two conditions, `without AI` and `with Copilot`
- Participants: `Professional Java developers`; 24 planned participants
- Task: `Fix two matched bugs in a Java service with a supplied test suite.`
- Session: 45 minutes; counterbalance the condition order
- Outcomes: time to first green and overall workload, using the available catalog

The count and session duration are presentation assumptions. Do not describe
them as a power-justified real study. A paired comparison does not model all
period or carryover effects; see [planner limits](planner.md).

The seeded example is named **Example: Copilot and bug fixing (synthetic data)**.
It has a saved protocol and plan, 24 illustrative links and 25 simulated
sessions. The defaults intentionally leave incomplete and flagged sessions
visible. Do not interpret the plotted differences as an observed Copilot effect.

## Fallbacks

- If chat is unavailable, use manual entry. The isolated launcher intentionally
  has no provider route; a provider-backed chat is a separate optional rehearsal.
- If manual entry takes too long, switch to the already populated example and
  inspect its saved protocol and plan. Skip typing rather than skipping the
  explanation of researcher approval.
- If the extension cannot be installed in the presentation environment, show
  the declared capture scope. State that an installed-editor session has not
  been demonstrated. Use a separate study and consented rehearsal for live pairing.
- If the live server is unavailable, use screenshots captured by
  `node platform/scripts/ui-regression.mjs --audit --screenshots /tmp/studyloop-showcase`.
  Call them screenshots of a synthetic rehearsal rather than a live session.

## Discussion prompts

For a presentation: ask which part of the workflow is most relevant to the
audience's work. For a research interview, use the neutral prompts in the
[interview guide](interview-study.md), elicit existing practice first, and record
post-demo reactions separately. Neither applause nor successful clicks establish
that the tool improves study quality.
