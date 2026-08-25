# Contributing to PHOENIX and TERN

Thanks for helping improve an open research tool. Contributions are welcome,
especially bug reports, reproducibility fixes, documentation, accessibility
improvements, and tests that make the participant boundary safer.

## Before opening a change

- Do not commit participant data, `.study-data/`, `results/`, local databases,
  API keys, or generated VSIX/build output.
- Keep capture content-free: no raw code, keystrokes, clipboard text, or
  off-workspace paths.
- Preserve the protocol contract: accepted design moves compile deterministically
  and schema or event-shape changes are versioned.

## Local gates

```bash
uv run ruff check .
uv run pytest
(cd extension && npm ci && npm run check)
(cd platform && npm ci && npm run check)
```

For platform changes, also run `npm run a11y` after installing Chromium. For
documentation changes, build the site with the command used by
`.github/workflows/docs.yml`.

## Pull requests

Explain what changed, why it matters, and which gates you ran. Changes to the
extension should update `extension/CHANGELOG.md`; changes that add or rename
platform agent markers should update `platform/docs/agent-annotations.md`.

Please use the issue templates for bugs and feature requests. Security and
participant-data reports must follow [SECURITY.md](SECURITY.md), not a public
issue.

By contributing, you agree that your work is offered under this repository's
[MIT License](LICENSE).
