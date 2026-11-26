# Install and run StudyLoop

StudyLoop runs on your own machine: one Python server that also serves the
PHOENIX web app. This page installs it, starts the example study and then your
own server. It takes a few minutes and needs no account or API key.

## What you need

- [Git](https://git-scm.com/downloads)
- [Node.js](https://nodejs.org/en/download) 22.13 or a newer LTS release
- [uv](https://docs.astral.sh/uv/getting-started/installation/), which also
  installs Python 3.12 for you

## Start the example study

```bash
git clone https://github.com/idreesshaikh/human-ai-studies-framework.git
cd human-ai-studies-framework
uv sync --package middleware --no-dev --frozen
npm --prefix platform ci
npm --prefix platform run build
uv run --no-sync python scripts/run_demo.py
```

Open <http://127.0.0.1:8000> and select **Example: Copilot and bug fixing (synthetic data)**.
The example runs on temporary storage with no model provider and no VS Code
extension. ++ctrl+c++ stops the server and deletes its data. Use `--port` to pick
another port.

To try the design conversation in the same disposable setup, add `--live`. The
conversation then sends requests to your model provider, which may cost money,
and can search Semantic Scholar when the bundled library is thin on a topic.
Literature suggestions start once the bundled paper corpus has loaded, about a
minute after the server starts.

```bash
uv run --no-sync --env-file .env.local python scripts/run_demo.py --live
```

`--live` needs a model. Create `.env.local` as described under
[Run your own server](#run-your-own-server), then add your key as shown in
[Connect a model](../reference/model-providers.md).

## Run your own server

Stop the example, copy the sample settings once, then start the regular server.

```bash
cp .env.example .env.local
uv run --no-sync --env-file .env.local python -m middleware
```

In PowerShell, use `Copy-Item .env.example .env.local` for the first line. Pass
`--env-file .env.local` every time you start the server, and restart it after you
change the file.

The sample settings listen on your own machine (`127.0.0.1`) and keep studies in
`.study-data/`. On first start StudyLoop imports the bundled paper corpus in the
background; literature suggestions and template rankings appear once
<http://127.0.0.1:8000/corpus/status> shows `"state": "ready"`.

Templates, entering the protocol directly, recruitment planning and exports all
work without a model. The [design conversation](../platform/design-conversation.md)
needs one.

!!! warning "Before participants on other machines connect"
    The sample server is for one researcher on a trusted machine. Participants on
    other machines need a server they can reach over HTTPS, with access controls
    you have set. See [Configuration](../reference/configuration.md) and the
    [security notes](https://github.com/idreesshaikh/human-ai-studies-framework/blob/main/SECURITY.md#access-and-capture).

## If something fails

If port 8000 is in use, run the example with `--port 8010`, or set
`MIDDLEWARE_PORT=8010` in `.env.local`. For a setup problem you want to report,
include your operating system, your Python and Node versions, and the command and
error. Use synthetic data in any reproduction.

## Next steps

- [Explore the example study](example-study.md) to see every tab with data in it.
- [Your first study](first-study.md) walks the path from an empty list to a participant link.
- [Connect a model](../reference/model-providers.md) to turn on the design conversation.
