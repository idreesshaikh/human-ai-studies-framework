# Archive — how this platform was built

This directory is the project's preserved build history. Nothing here is
needed to *use* the platform (start at the [root README](../../README.md));
everything here documents *how it came to exist*, and is kept intact for
examination and provenance. **The current direction is
[`docs/VISION.md`](../VISION.md)** (v2, 2026-07-17 — the conversational
research platform); everything below is the superseded-but-authoritative
record of the v1 engine that direction builds on.

- **`roadmap/00-VISION.md`** — the v1 vision, architecture argument,
  and the one-week sprint plan (superseded banner at top; its tracker
  stays authoritative for MP-01..13).
- **`roadmap/01..13`** — the executable phase specifications
  ("mega-prompts") the v1 engine was built from, in order. Each states
  its goals, deliverables, acceptance criteria, and verification steps.
  Their completion records live in
  [`requirements/traceability.md`](../../requirements/traceability.md).
  The v2 phases (MP-14..18) are not yet specced; when written they land
  in a live `docs/roadmap/` (not this archive) and are indexed from the
  v2 vision.

The platform was developed as a requirements-engineering Masters project:
every feature traces to a numbered requirement in
[`requirements/`](../../requirements/), and every reuse decision is argued
in [`requirements/build-vs-adopt.md`](../../requirements/build-vs-adopt.md).
The public docs deliberately stay in plain language; this layer is where
the formal record lives.
