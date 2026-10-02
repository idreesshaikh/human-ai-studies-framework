# Requirements

What the artifact needs to run, and what it deliberately does not.

## Hardware

No special hardware. The artifact was developed and evaluated on a laptop.

| Resource | Minimum | Notes |
| --- | --- | --- |
| Disk | 3 GB | Dependency caches dominate; the SQLite study database is a few MB. |
| Memory | 4 GB | The paper index imports in a background thread on first start. |
| CPU | Any x86-64 or Apple Silicon | No GPU. No accelerator. Nothing is trained. |
| Network | Optional | Needed only for dependency install and the two optional features below. |

## Software

| Requirement | Version | Why |
| --- | --- | --- |
| Python | 3.12+ | Pinned in `.python-version`. |
| [uv](https://docs.astral.sh/uv/) | current | Resolves the workspace from the committed `uv.lock`. |
| Node.js | 22+ | Builds the researcher web workspace. |
| Git | any | Used by the repository size check in CI. |

Docker is an alternative to all of the above: `docker compose up --build`
starts the app, PostgreSQL, and a synthetic demo.

Tested on macOS (Darwin 27) and Ubuntu (GitHub Actions runners). Nothing in the
artifact is platform-specific, but Windows is untested.

## No credentials required

The artifact runs fully offline after dependency install. Storage defaults to a
local SQLite file at `.study-data/middleware.sqlite3`; no database service is
needed. Template loading, protocol validation, participant assignment, capture
configuration, dataset export, the analysis recipes, the notebook, and the
local corpus search all work with no API key.

Two features are optional and disabled without a key:

- **Design conversation.** Sets `MISTRAL_API_KEY` to have a model propose
  protocol changes. Without it, the same protocols are built from templates.
  The model can never bypass protocol validation.
- **External paper lookup.** Enriches the local corpus from Semantic Scholar.
  The bundled index works without it.

A reviewer can evaluate every claim in the paper without obtaining either key.

## Data

No participant data is included, and none is required. The repository contains
no human-subjects data of any kind.

The dry-run generator produces labelled synthetic sessions for rehearsing the
capture and analysis path. Every synthetic row carries `synthetic: true`, and
`analysis run` banners any report computed from such rows and refuses a
non-zero exit on datasets that mix synthetic and participant rows. Synthetic
output demonstrates that the pipeline connects; it is not a research finding
and the tool will not let it be presented as one.

## Not required

No cluster, no institutional access, no ethics approval, and no proprietary
dataset are needed to run or evaluate this artifact. Ethics approval is
required to run a *study* with it, which is outside the artifact's scope.
