# PHOENIX · Human–AI Study Framework

## From a research idea to a study you can trust

PHOENIX is the researcher-facing half of the framework: a grounded design
conversation, a deterministic protocol compiler, a participant hand-off, and a
curated analysis path in one place. **TERN** is the participant-facing half: a
small VS Code extension that runs the approved study and records only the
signals the protocol permits.

<figure markdown="span">
  ![The current Phoenix home page](assets/screens/phoenix-home-current.png){ width="900" }
  <figcaption>Start with the question, not a blank form. PHOENIX turns plain language into explicit, reviewable study decisions.</figcaption>
</figure>

## The whole project, in one spine

| Researcher action | PHOENIX provides | TERN provides |
| --- | --- | --- |
| Frame the question | Literature-grounded design moves with citations or an explicit unsourced label | — |
| Freeze the method | A versioned protocol, validation, consent statement, and capture configuration | Reads only the approved configuration |
| Rehearse the study | Synthetic participants through the real ingest and analysis path | — |
| Invite a participant | A one-use pairing link and counterbalanced task assignment | Installs the study into VS Code after consent |
| Run the session | Live session and integrity visibility | Timer, probes, behaviour signals, local JSONL, optional HTTP mirror |
| Make the result portable | Curated data, dictionary, analysis recipes, notebook and paper hand-off | — |

That separation is the thesis in product form: the platform makes the method
explicit and reproducible; the extension makes the participant experience
lightweight and privacy-preserving; the middleware makes the boundary between
them observable.

## What PHOENIX protects

- **Methodological coherence.** Accepted design moves compile into the protocol
  that configures the session. The chat cannot silently outrank the draft.
- **Evidence traceability.** Each grounded move carries its paper and confidence;
  a missing source is shown as missing rather than dressed up as certainty.
- **Participant dignity.** TERN records sizes, shapes, and timings—not raw code,
  keystrokes, clipboard text, or off-workspace paths. The consent statement and
  preflight summary are generated from the same approved capture config.
- **Analysis readiness.** A synthetic dry run exercises the real capture path
  before recruitment, while sequence gaps and incomplete sessions remain visible
  instead of being quietly smoothed away.

## Two products, one workflow

- **[Platform](platform/index.md)** — design, compile, rehearse, recruit, curate.
- **[TERN Extension](extension/index.md)** — pair, consent, work, probe, debrief.

The [platform quick start](platform/quickstart.md) is the fastest route through
the complete loop. If you are a participant, start with [Installing TERN](extension/install.md).

## Try the release locally

Prerequisites: [uv](https://docs.astral.sh/uv/), Node 22, and a
[Mistral API key](https://console.mistral.ai/) for the design conversation.
PHOENIX uses Mistral Large (`mistral-large-latest`) as its only model route.

```bash
git clone https://github.com/idreesshaikh/human-ai-studies-framework.git
cd human-ai-studies-framework
uv sync --all-packages
(cd platform && npm ci && npm run build)
echo "MISTRAL_API_KEY=sk-..." >> .env
uv run python -m middleware corpus-import
uv run python -m middleware serve
```

Open <http://localhost:8000>, or run the
[TERN lab on GitHub](https://github.com/idreesshaikh/human-ai-studies-framework/tree/main/extension/examples/tern-lab)
in VS Code to see the participant side without pairing a real study.

!!! warning "Demo data is not a finding"
    The checked-in demo study and screenshots are synthetic fixtures. They exist
    to make the workflow tangible and to exercise integrity states; they must
    never be reported as empirical results.
