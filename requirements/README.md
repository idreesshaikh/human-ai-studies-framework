# Requirements - the RE foundation of the platform

This directory is the root of all traceability in the project. The platform
claims that a study protocol is a requirements specification - and that a
**design conversation is requirements elicitation** (`docs/VISION.md`);
these artifacts requirements-engineer the platform itself, so the claim is
practiced, not just stated.

## Artifacts and how they relate

| File / dir               | What it is                                            | Feeds into                     |
| ------------------------ | ----------------------------------------------------- | ------------------------------ |
| `glossary.md`            | Controlled vocabulary - all documents use these terms | everything                     |
| `stakeholders.md`        | Who wants what (S1–S7), and where goals conflict      | research questions, SRS        |
| `research-questions.md`  | Framework RQs (thesis) + pilot RQs (evaluation)       | SRS rationale, analysis plan   |
| `srs.md`                 | Functional + non-functional requirements, MoSCoW - **the index of record** | every phase spec |
| `specs/`                 | Detailed specifications per family: data models, numbered fit criteria, degradation posture, paper grounding | phase specs |
| `traceability.md`        | The living matrix: RQ → REQ → component → data → analysis, plus REQ → status | updated at the end of every phase |
| `build-vs-adopt.md`      | Every reuse decision: adopt / adapt / build / reject + rationale (NFR-10) | phase specs, dependency changes |
| `metric-coverage.md`     | Literature-grounded audit mapping every metric family to a leg (captured / specified / gap / excluded) | instrument requirements |

## Rules

1. **No orphan work.** Every implementation phase cites the requirement
   IDs it satisfies; every Must requirement is owned by a phase.
2. **IDs are stable anchors.** Don't renumber requirement or decision IDs;
   drop a requirement cleanly and update its references instead.
3. **The matrix is living.** Completing a phase means flipping status
   cells in `traceability.md` - a phase is not done until the matrix says
   so.
4. **Glossary wins.** Terminology disputes are settled by `glossary.md`;
   change the glossary, then the documents.
5. **Rows over specs.** Where a `specs/` document and its `srs.md` row
   disagree, the row wins and the drift is a logged defect (FR-META-1).
