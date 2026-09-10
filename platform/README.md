# PHOENIX web workspace

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

Workspace changes require the server. Some read-only demo views have labelled
bundled examples; they cannot create projects or participant links. The design
conversation requires `MISTRAL_API_KEY` on the server.

See [development](docs/development.md), the
[design guide](../docs/design.md), and the
[framework architecture](../docs/architecture.md).
