# Requirements - the RE foundation of the platform

This directory is the root of all traceability in the project. The platform
claims that a study protocol is a requirements specification
(`docs/archive/roadmap/00-VISION.md`); these artifacts requirements-engineer the platform
itself, so the claim is practiced, not just stated.

## Artifacts and how they relate

| File                     | What it is                                            | Feeds into                     |
| ------------------------ | ----------------------------------------------------- | ------------------------------ |
| `glossary.md`            | Controlled vocabulary - all documents use these terms | everything                     |
| `stakeholders.md`        | Who wants what, and where goals conflict              | research questions, SRS        |
| `research-questions.md`  | Framework RQs (thesis) + pilot RQs (evaluation)       | SRS rationale, analysis plan   |
| `srs.md`                 | Functional + non-functional requirements, MoSCoW      | every mega-prompt in `docs/archive/roadmap/`|
| `traceability.md`        | The living matrix: RQ → REQ → component → data → analysis, plus REQ → phase → status | updated at the end of every phase |

## Rules

1. **No orphan work.** Every implementation phase (`docs/archive/roadmap/02`–`09`) cites
   the requirement IDs it satisfies; every Must requirement is owned by a
   phase.
2. **IDs are stable.** Never renumber; deprecate with a strikethrough and a
   note instead.
3. **The matrix is living.** Completing a phase means flipping status cells
   in `traceability.md` - a phase is not done until the matrix says so.
4. **Glossary wins.** Terminology disputes are settled by `glossary.md`;
   change the glossary, then the documents.
