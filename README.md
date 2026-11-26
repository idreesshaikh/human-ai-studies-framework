<p align="center">
  <img src="platform/public/favicon.svg" alt="" width="64" height="64">
</p>

<h1 align="center">StudyLoop</h1>

<p align="center">Design, run, and analyse studies of developers working with AI.</p>

<p align="center">
  <a href="#quickstart">Quickstart</a> ·
  <a href="#connect-a-model">Connect a model</a> ·
  <a href="#the-workflow">Workflow</a> ·
  <a href="#documentation">Documentation</a> ·
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

StudyLoop helps researchers run studies of developers working with and without AI.
**PHOENIX**, the researcher web app, turns a research question into a protocol and
shows the data it produces. **TERN**, a VS Code extension, runs that protocol with
each participant and records what it allows.

![PHOENIX Setup with the study design conversation beside the protocol draft](documentation/docs/assets/screens/setup.webp)

## Quickstart

Install Git, [Node.js 22.13+ or a newer LTS release](https://nodejs.org/en/download),
and [uv](https://docs.astral.sh/uv/getting-started/installation/). StudyLoop uses
Python 3.12, which uv can install for you.

```sh
git clone https://github.com/idreesshaikh/human-ai-studies-framework.git
cd human-ai-studies-framework
uv sync --package middleware --no-dev --frozen
npm --prefix platform ci
npm --prefix platform run build
uv run --no-sync python scripts/run_demo.py
```

Open <http://127.0.0.1:8000> and select **Example: Copilot and bug fixing
(synthetic data)**. The example needs no account, API key, or VS Code extension,
and every session in it is simulated. Ctrl+C stops the server and removes its temporary data.
[Explore the example study](documentation/docs/get-started/example-study.md)

### Keep your own studies

Stop the example, copy the settings file once, then start the regular server.

```sh
cp .env.example .env.local
uv run --no-sync --env-file .env.local python -m middleware
```

In PowerShell, use `Copy-Item .env.example .env.local` for the first line. The
sample settings listen on your own machine and save studies in `.study-data/`.
Templates, direct protocol entry, recruitment planning, and exports work without a
model. The bundled literature index fills in the background on the first run.
[Server configuration](documentation/docs/reference/configuration.md)

## Connect a model

The design conversation needs a language model. Edit `.env.local`, then restart the
server with the same `--env-file` command. Keep credentials in that local file,
which Git ignores.

**Mistral.** In Mistral Studio, open **API Keys**, choose **New key**, and copy it
into `.env.local`. StudyLoop uses its default Mistral model unless you set
`LLM_MODEL`. [Mistral's API key guide](https://docs.mistral.ai/getting-started/quickstarts/studio/activate-and-generate-api-key)

```dotenv
LLM_API_KEY=your-mistral-key
```

**Ollama on your machine.** [Install Ollama](https://ollama.com/download), start it,
and pull a model such as [`qwen2.5:7b`](https://ollama.com/library/qwen2.5:7b) with
`ollama pull qwen2.5:7b`.

```dotenv
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_MODEL=qwen2.5:7b
LLM_API_KEY=
```

**Another OpenAI-compatible provider.** Set `LLM_BASE_URL` to the provider's HTTPS
API base, `LLM_API_KEY` to its key, and `LLM_MODEL` to the exact model ID. Choose a
chat model that supports JSON output through `response_format: json_object`.

Hosted providers receive the text of the design conversation and the retrieved
literature. Keep participant details out of design prompts and review your
provider's data terms. When the bundled library has little on a topic, a design
turn also sends a few keywords from your messages to Semantic Scholar; set
`MIDDLEWARE_LIVE_SEARCH=0` to stop that.
[All model settings and troubleshooting](documentation/docs/reference/model-providers.md)

## The workflow

A study has five tabs in PHOENIX, in the order you usually need them.

| Tab | What you do |
| --- | --- |
| **Setup** | Describe the study in the design conversation, start from a template, or enter the details directly. Review the compiled protocol and apply it: Plan, Run and Data need it |
| **Literature** | Collect the papers behind your design and link them to protocol decisions |
| **Plan** | State your assumptions and save a recruitment estimate against the protocol |
| **Run** | Create participant links and give participants the TERN extension. Capture starts after consent |
| **Data** | Inspect capture coverage, record pilot and inclusion decisions, and export data, a notebook, or a replication kit |

Participants on other machines need a server they can reach over HTTPS and a TERN
build that matches your study. [Give participants TERN](documentation/docs/platform/give-participants-tern.md)

Sample-size estimates depend on your assumptions. TERN's editor and tool signals are
observations whose error rates have not been measured, so they need independent
validation before you draw conclusions about AI use, and they cannot show that a
control group stayed free of AI. Synthetic sessions are excluded from default
research exports and estimates.
[Scope and limits](documentation/docs/reference/scope.md)

## Documentation

- **Researchers:** [Get started](documentation/docs/get-started/index.md), then
  [design a study](documentation/docs/platform/index.md),
  [plan recruitment](documentation/docs/platform/planning.md),
  [run it](documentation/docs/platform/participants.md), and
  [read the data](documentation/docs/platform/data.md).
- **Participants:** [install and connect TERN](documentation/docs/extension/install.md)
  and [see what it captures](documentation/docs/extension/captured-data.md).
- **Reference:** [architecture](docs/architecture.md),
  [planner methods](docs/planner.md), [scope](docs/scope.md), and
  [server configuration](documentation/docs/reference/configuration.md).

To read the guide as a site, run `uv sync --all-packages --group docs --frozen`,
then `uv run --no-sync mkdocs serve -f documentation/mkdocs.yml`.

## Contributing, licence, and citation

Read the [contributing guide](CONTRIBUTING.md) before you open a pull request, and
report vulnerabilities through the [security policy](SECURITY.md). If a setup step
fails, [open an issue](https://github.com/idreesshaikh/human-ai-studies-framework/issues/new/choose)
with your operating system, your Python and Node versions, and the command and
error. Use synthetic data in reproductions.

StudyLoop is available under the [MIT License](LICENSE). If you use it in research,
cite the software and record the revision you ran: see [CITATION.cff](CITATION.cff).
