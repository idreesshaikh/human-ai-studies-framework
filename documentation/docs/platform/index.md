# PHOENIX

PHOENIX is the web app where researchers design a study, connect participants,
and read what TERN recorded. The app itself is titled **StudyLoop**.

<figure markdown="span">
  ![The Setup tab of the example study, with the Setup, Evidence, Plan, Run and Data tabs along the top and the protocol draft open on the right](../assets/screens/setup-light.webp#only-light)
  ![The Setup tab of the example study, with the Setup, Evidence, Plan, Run and Data tabs along the top and the protocol draft open on the right](../assets/screens/setup-dark.webp#only-dark)
  <figcaption>Setup, the first of five tabs in every study, with the protocol draft open.</figcaption>
</figure>

## A study, tab by tab

Each study opens on five tabs, in the order you usually need them.

| Tab | What you do there | Guide |
| --- | --- | --- |
| **Setup** | Describe the study in the design chat, or enter it directly, then review and apply the protocol | [Design chat](design-conversation.md), [Protocol draft](protocol-draft.md) |
| **Evidence** | Collect the papers behind the study and link them to the protocol | [Evidence](library.md) |
| **Plan** | Estimate how many participants the analysis needs | [Plan](planning.md) |
| **Run** | Create participant links and watch sessions as they run | [Participant links](participants.md) |
| **Data** | Check captured sessions, record inclusion decisions, and download the records | [Data](data.md) |

**Share** in the study header downloads the data bundle (**Data (.zip)**), the
**Replication kit**, the **Elicitation record** and a **Starter notebook**.
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

You need Python 3.12 or later, Node.js 22 or later, and
[uv](https://docs.astral.sh/uv/).

### The example study

The example runs on temporary storage and needs no API key.

```bash
uv sync --all-packages --frozen
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

```bash
cp .env.example .env.local
MIDDLEWARE_API_ONLY=1 uv run --no-sync --env-file .env.local python -m middleware
npm --prefix platform run dev    # in a second terminal
```

Open <http://localhost:5173>. The server keeps its data in `.study-data/`. On
first start it imports the bundled paper corpus in the background, which takes
about a minute; literature suggestions appear once
<http://127.0.0.1:8000/corpus/status> reports `"ready"`. To serve everything
from one process instead, build the web app, start the server without
`MIDDLEWARE_API_ONLY=1`, and open <http://127.0.0.1:8000>.

| Setting | What it does |
| --- | --- |
| `LLM_API_KEY` | Turns on the design chat. Without a model, the chat is off and everything else works |
| `LLM_BASE_URL` | A chat-completions server to use instead. A local server needs no key |
| `LLM_MODEL` | The model. The default is `ministral-14b-latest` on Mistral's API |
| `LLM_DESIGN_MODEL` | A different model for the design chat only |
| `MIDDLEWARE_AUTH` | Unset: no sign-in, for one researcher. `token`: require `MIDDLEWARE_TOKEN`. Setting `MIDDLEWARE_TOKEN` alone also turns on token mode |

The server does not read `.env.local` by itself; pass it with `--env-file` as
above. The [server guide](https://github.com/idreesshaikh/human-ai-studies-framework/blob/main/middleware/README.md)
covers storage and the remaining settings.
