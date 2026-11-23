---
hide:
  - navigation
---

# StudyLoop

StudyLoop helps researchers design, run and inspect studies of developers
working with and without AI. **PHOENIX**, the researcher web app, turns a
research question into a versioned protocol. **TERN**, an extension for VS Code,
runs that protocol with each participant and records what it allows.

<div class="grid cards" markdown>

-   **For researchers**

    ---

    Design the protocol, connect participants and read the data in PHOENIX.

    [Start a study](platform/quickstart.md)

-   **For participants**

    ---

    Install TERN in VS Code and connect it with the link you were sent.

    [Install and connect](extension/install.md)

</div>

<figure markdown="span">
  ![The example study in PHOENIX, on its Data tab](assets/screens/data-light.webp#only-light)
  ![The example study in PHOENIX, on its Data tab](assets/screens/data-dark.webp#only-dark)
  <figcaption>The example study that ships with StudyLoop. Its sessions are synthetic.</figcaption>
</figure>

## How a study moves through StudyLoop

| Step | PHOENIX | TERN |
| --- | --- | --- |
| Design | The design chat proposes decisions, each backed by papers or marked as your call. Or enter the design directly | — |
| Apply | Compiles and checks a versioned protocol, with its consent statement and capture settings | — |
| Plan | Estimates recruitment from assumptions you state | — |
| Connect | Creates participant links and assigns conditions | Shows the consent statement, then locks to the study's settings |
| Run | Shows each running session's event rate and gaps | Runs the clock and the questions, records editor activity, writes a local file first and sends it to the server |
| Analyse | Checks integrity, records inclusion decisions, exports data and replication kits | — |

The protocol you apply is the only thing that configures a participant's
session, so the study you designed is the study that runs.

## What StudyLoop does not claim

- **AI use.** TERN records accepted inline suggestions, and agent activity from
  hooks you install. It cannot verify that a no-AI group stayed free of AI.
  Pastes, fast bulk edits and provider queries are ambiguous, and a missing
  signal does not show that no AI was used.
- **Validity.** Calculations depend on the assumptions shown beside them.
  StudyLoop does not certify a study, and it does not replace ethics review or
  statistical judgement.
- **Results from examples.** Synthetic sessions are left out of research
  exports and estimates.

!!! warning "Example data is not a finding"
    The example study and every screenshot in this guide use synthetic data.
    They show how the workflow looks and must never be reported as results.

## Try it

The example study runs locally with no API key:

```bash
uv sync --all-packages --frozen
npm --prefix platform ci
npm --prefix platform run build
uv run --no-sync python scripts/run_demo.py
```

Open <http://127.0.0.1:8000>. [Run PHOENIX yourself](platform/index.md#run-phoenix-yourself)
covers the design chat, your own server and its settings. To see TERN without a
study, open the [TERN lab](extension/index.md#try-it-without-a-study).

This guide is for people using StudyLoop. Architecture and development notes
are in the repository's
[`docs/`](https://github.com/idreesshaikh/human-ai-studies-framework/tree/main/docs)
folder.
