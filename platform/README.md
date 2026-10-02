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

All study reads and writes require the server, including the read-only demo.
Failed requests show errors; the browser never substitutes sample results. The design
conversation requires `MISTRAL_API_KEY` on the server.

See [development](docs/development.md), the
[design guide](../docs/design.md), and the
[framework architecture](../docs/architecture.md).
