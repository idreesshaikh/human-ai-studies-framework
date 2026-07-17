# Detailed specifications (the spec tree)

`../srs.md` is the **index of record**: stable IDs, one-line requirement
statements, MoSCoW, status. Each v2 family additionally owns a detailed
specification here — elaboration, data models, API surfaces, fit criteria
(numbered, testable), degradation behavior, privacy analysis, and paper
grounding. **The SRS row wins on conflict**; a spec that drifts from its
row is a defect (log it, FR-META-1).

| Spec | Family | Phase |
| ---- | ------ | ----- |
| `fr-conv.md` | Conversational study design — *the platform's core interaction* | MP-15 (core), MP-18 (evolution) |
| `fr-tpl.md` | Study templates & statistical plans | MP-15 |
| `fr-cur.md` | Curated datasets & mining | MP-16 |
| `fr-plat.md` | Platform shell: projects, roles, hero | MP-14 |
| `fr-agf.md` | Agent-friendliness: manifest & context files | MP-17 |
| `nfr-12-experience.md` | Experience quality: design system, motion, chat surfaces | binds MP-14..18 |
| `fr-lit-v2.md` | Corpus at scale (tiers, harvest pipeline), idea→paper matching, living literature view | pipeline built; MP-15/17 |

Design elaboration (diagrams, UI/motion contracts) lives in
`docs/design/` — subordinate to these specs as these are to the SRS.

Rules: specs follow the glossary (golden rule 4); every fit criterion is
phrased so a test or demo can pass/fail it (RE fit-criterion discipline);
paper citations use the corpus index (`docs/papers/README.md`) file slugs.
Specs are versioned by dated rev notes, IDs inside them never renumber
(golden rule 2).
