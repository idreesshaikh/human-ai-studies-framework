# Product terminology

Keep API and historical template IDs stable. Improve visible labels without
renaming stored records or silently changing a study's design.

| Term | Meaning |
| --- | --- |
| Study | One protocol, participant assignments, and attributed dataset |
| Protocol | The current executable specification |
| Draft | A preview; not the configuration enrollment currently uses |
| Decision | A proposal accepted, rejected, or corrected by a researcher |
| Condition | The experimental setting; not a participant or task |
| Block | One assigned task under one condition |
| Participant link | A credential used to pair TERN; not proof of participation |
| Synthetic rehearsal | Simulated capture for testing, never participant findings |
| Model grounding | Retrieved source provenance, not validated methodological support |

UI actions say **Create participant links**, not “mint”. Link counts do not
claim that people have joined or completed sessions. Plan distinguishes accepted
decision previews from the current protocol used in Run. Assignment remains
deterministic; counterbalancing does not establish random allocation.

Regression coverage: `middleware/tests/test_run_plan.py`,
`middleware/tests/test_authz.py`, and the browser rehearsal described in
[demo readiness](demo-readiness.md). Issue #62 also covers historical schemas and
templates; this glossary and UI pass do not claim a complete schema migration.
