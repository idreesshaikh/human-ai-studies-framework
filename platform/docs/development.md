# Frontend development

The researcher workspace uses React, TypeScript, Vite, Tailwind, and vendored
Radix-based components. The server supplies study data and validates changes.
Start with the [repository setup](../../README.md) and
[architecture](../../docs/architecture.md).

## Find the code

| Location | Responsibility |
| --- | --- |
| `src/App.tsx` | Routes and authentication boundary |
| `src/pages/` | Projects, study workspace, templates, settings |
| `src/components/conversation/` | Design proposals and protocol review |
| `src/components/library/` | Papers and citation graph |
| `src/components/charts/` | Data, timelines, and planning |
| `src/components/enrollment/` | Participant links and capture settings |
| `src/lib/api.ts` | HTTP client, shared credentials, connection errors |
| `src/lib/session.tsx` | API and signed-in identity contexts |
| `src/lib/compiler.ts` | Advisory browser preview of accepted decisions |
| `src/styles/` | Design tokens and common styles |

Run the middleware on port 8000 and `npm run dev` here. The Vite proxy keeps API
requests on the same origin during development. Production serves `dist/`
through the middleware. Set `VITE_API_BASE` only for a separate API origin.

## Data and state

`useApi()` provides the HTTP client for projects, members, and enrollment.
`studyApi.ts`, `conversationApi.ts`, and `templatesApi.ts` handle workspace
requests. They share the authentication token provider. A 401 tells the auth
layer to show sign-in; network failure does not create temporary projects or
participant links.

Some read-only demo views include labelled bundled examples. The conversation
requires a model and reports when one is unavailable.

Component state holds drafts and selection. `useAsync` handles loading, errors,
and retry, including a retry after credentials become available. It has no cache
or request deduplication.

## Make a change

Add pages under `src/pages/` and declare their routes in `App.tsx`. Avoid API
path collisions: the project page is `/home`, while `/projects` is an API.
Use the existing components and [design guide](../../docs/design.md).

The browser compiler mirrors part of `middleware/compiler.py`. When changing
move types or compilation rules, check both; only server validation permits
applying a protocol.

Run `npm run check` for lint, type checking, behavior checks, and a production
build. Run `npm run a11y` for browser accessibility checks. Add targeted tests
for changed behavior rather than tests that repeat component markup.
