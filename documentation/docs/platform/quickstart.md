# Quick start

Run the whole stack locally in four commands. Prerequisites:
[uv](https://docs.astral.sh/uv/), Node 22, and a
[Mistral API key](https://console.mistral.ai/) (needed only for the design
conversation).

## Local setup

```bash
git clone https://github.com/idreesshaikh/human-ai-studies-framework.git
cd human-ai-studies-framework

uv sync --all-packages
(cd platform && npm ci && npm run build)

echo "MISTRAL_API_KEY=sk-..." >> .env

uv run python -m middleware corpus-import   # load the 15,000-paper index
uv run python -m middleware serve           # web app on :8000
```

Open <http://localhost:8000>. Without `MIDDLEWARE_AUTH` set, the server runs
in local mode without authentication.

!!! tip "Docker"
    `docker compose up` brings the whole stack up with its own Postgres —
    no local Python or Node install needed.

## Your first study

<figure markdown="span">
  ![Project list](assets/screens/projects.png){ width="800" }
  <figcaption>Your projects — create one or browse proven designs first.</figcaption>
</figure>

1. **Start a project** from the home page, or browse the
   [protocol repertoire](library.md) first to see proven design shapes.
2. Open the project and describe your research idea in the
   [design conversation](design-conversation.md).
3. Rule on the proposals one at a time — accept or reject, watching the
   [protocol draft](protocol-draft.md) compile beside you.
4. Move through gates and ethics, then open **Participants** to create
   participant links that configure TERN on each machine.
5. Use the **Data** tab to dry-run the capture path and hand the dataset off to
   your own notebook with the exact test to run.

## The CLI, end to end

The same paths the web app drives are one command each (all take
`MIDDLEWARE_TOKEN` for auth and `--server` to point elsewhere):

```bash
uv run python -m middleware simulate pilot-2026 --count 10 --seed 42
# simulated 10 participants (mixed): 20 sessions, 713 events, …
# plan validation: 4 recipe(s) ran, 0 check(s) failed; report under results/

uv run python -m analysis.cli run protocol/examples/pilot-study.yaml --server http://127.0.0.1:8000
uv run python -m analysis.cli notebook protocol/examples/pilot-study.yaml --server http://127.0.0.1:8000
uv run python -m analysis.cli paper protocol/examples/pilot-study.yaml
```

- `simulate` — synthetic dry run over plain HTTP, then validates the study's
  analysis plan against the synthetic data. Exit 0 only when every planned
  recipe ran.
- `notebook` — the curated handoff: `results/<study>/notebook.ipynb` (a loaded,
  documented dataframe with every planned recipe imported — never run) plus a
  standalone `data-dictionary.md`.
- `paper` — a first-draft Methods + Results paper section, from the same plan.
- `run` / `validate` / `list` — execute recipes, check plan satisfaction, and
  catalogue what exists (`uv run python -m analysis.cli --help`).