# Platform

The PHOENIX platform is the web application where a study is designed, compiled,
and coordinated — from the first research idea to the participant links that
configure TERN on each machine.

<figure markdown="span">
  ![The platform home](assets/screens/hero.png){ width="800" }
  <figcaption>The hero: describe an idea in plain language.</figcaption>
</figure>

## What the platform covers

- **Design** — a structured conversation with the design assistant. Every
  proposal is either cited into the corpus or plainly marked unsourced; there
  is no third state.
- **Compile** — accepted moves compile deterministically into a versioned
  protocol, diffed, validated, and applied only on your approval.
- **Coordinate** — projects, roles, invitations, participants, and the
  participant links that install the study on each editor.
- **Catalogue** — curated data, per-RQ reports, a data dictionary, and a
  starter notebook with the exact test to run.

## Core pages

| Page | What it does |
| --- | --- |
| [Home](quickstart.md) | Your projects and templates |
| [Design conversation](design-conversation.md) | Talk the study into existence |
| [Protocol draft](protocol-draft.md) | The compiled protocol, live beside the conversation |
| [Participants](participants.md) | Rotate task order, create participant links |
| [Data](data.md) | Collection, dry runs, curation, analysis handoff |
| [Library](library.md) | The protocol repertoire and literature constellation |

## Authentication & local setup

The platform uses Clerk for authentication in production. Locally you can run
it without auth by leaving `MIDDLEWARE_AUTH` unset — the server serves the
built app at `http://localhost:8000` in a single process.

```bash
uv sync --all-packages
(cd platform && npm ci && npm run build)
uv run python -m middleware corpus-import   # load the 15,000-paper index
uv run python -m middleware serve           # web app on :8000
```

A Mistral API key is needed only for the design conversation; everything else
works without one. See the [quick start](quickstart.md) for the full setup.