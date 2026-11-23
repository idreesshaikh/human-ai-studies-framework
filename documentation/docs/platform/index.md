# PHOENIX

PHOENIX is the web app where researchers design a study, connect participants,
and read what TERN recorded. The app itself is titled **StudyLoop**.

## A study, tab by tab

Each study opens on five tabs, in the order you usually need them.

| Tab | What you do there | Guide |
| --- | --- | --- |
| **Setup** | Describe the study in the design chat, or enter it directly, then review and apply the protocol | [Design chat](design-conversation.md), [Protocol draft](protocol-draft.md) |
| **Literature** | Collect the papers behind the study and link them to the protocol | [Literature](library.md) |
| **Plan** | Estimate how many participants the analysis needs | [Plan](planning.md) |
| **Run** | Create participant links and watch sessions as they run | [Participant links](participants.md) |
| **Data** | Check captured sessions, record inclusion decisions, and download the records | [Data](data.md) |

**Export** in the study header offers the data bundle, design card, replication
kit, elicitation record and starter notebook. The Data tab also offers the first
three downloads.
The **?** button next to it opens a short tour of the workspace.

## How PHOENIX and TERN connect

The applied protocol is the only thing that configures a participant's session.

```text
Protocol in PHOENIX
   │  consent statement, capture settings, assigned condition
   ▼
TERN in VS Code ── writes a local file first ──► study server ──► Data tab
```

[Participant links](participants.md) covers the hand-off and
[TERN's captured data](../extension/captured-data.md) covers every event.

## Run PHOENIX yourself

Install Git, Node.js 22.13+ or a newer LTS release, and
[uv](https://docs.astral.sh/uv/getting-started/installation/). uv can install
Python 3.12 for you.

### The example study

The example runs on temporary storage and needs no API key.

```bash
git clone https://github.com/idreesshaikh/human-ai-studies-framework.git
cd human-ai-studies-framework
uv sync --package middleware --no-dev --frozen
npm --prefix platform ci
npm --prefix platform run build
uv run --no-sync python scripts/run_demo.py
```

Open <http://127.0.0.1:8000>. ++ctrl+c++ stops the server and deletes its data.
Use `--port` to pick another port. The design chat is off in this mode; to try
it with your model provider and the paper corpus, add `--live` and pass your
settings file:

```bash
uv run --no-sync --env-file .env.local python scripts/run_demo.py --live
```

`--live` sends requests to your model provider, which may cost money.

### Your own server

Stop the demo. Copy the sample settings once, then start the regular server.

```bash
cp .env.example .env.local
uv run --no-sync --env-file .env.local python -m middleware
```

In PowerShell, use `Copy-Item .env.example .env.local` to copy the file. Open
<http://127.0.0.1:8000>. The sample binds to loopback and keeps studies in
`.study-data/`. On first start, StudyLoop imports the bundled paper corpus in
the background. Literature suggestions appear once
<http://127.0.0.1:8000/corpus/status> reports `"ready"`.

Configure Mistral, Ollama, or another compatible provider in `.env.local` to
enable the design conversation. Templates and manual setup work without a
model. Pass the settings file with `--env-file` whenever you start the server.
[Connect a model](https://github.com/idreesshaikh/human-ai-studies-framework#connect-a-model) ·
[Server configuration](https://github.com/idreesshaikh/human-ai-studies-framework/blob/main/middleware/README.md)
