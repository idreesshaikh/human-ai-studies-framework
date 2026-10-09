# PHOENIX web workspace

PHOENIX is the researcher platform in the StudyLoop project.

The researcher interface for study design, protocol review, participant setup,
literature, and data export. Built with React, TypeScript, Vite, and Tailwind.

Start the middleware on port 8000, then run:

```bash
npm ci
npm run dev
```

Vite proxies API requests to the middleware. A built app is served by the
middleware at the same origin:

```bash
npm run check
npm run build
```

Workspace changes require the server. Unavailable data is reported explicitly.
The design conversation uses the server's configured provider: `LLM_API_KEY`
for a hosted API, or `LLM_BASE_URL` for a compatible local server. The existing
`MISTRAL_API_KEY` alias remains supported.

See [development](docs/development.md), the
[design guide](../docs/design.md), and the
[framework architecture](../docs/architecture.md).
