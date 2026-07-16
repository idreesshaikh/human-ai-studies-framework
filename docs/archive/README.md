# Archive — how this platform was built

This directory is the project's preserved build history. Nothing here is
needed to *use* the platform (start at the [root README](../../README.md));
everything here documents *how it came to exist*, and is kept intact for
examination and provenance.

- **`roadmap/00-VISION.md`** — the original vision, architecture argument,
  and the one-week sprint plan.
- **`roadmap/01..12`** — the twelve executable phase specifications
  ("mega-prompts") the platform was built from, in order. Each states its
  goals, deliverables, acceptance criteria, and verification steps. Their
  completion records live in
  [`requirements/traceability.md`](../../requirements/traceability.md).

The platform was developed as a requirements-engineering Masters project:
every feature traces to a numbered requirement in
[`requirements/`](../../requirements/), and every reuse decision is argued
in [`requirements/build-vs-adopt.md`](../../requirements/build-vs-adopt.md).
The public docs deliberately stay in plain language; this layer is where
the formal record lives.
