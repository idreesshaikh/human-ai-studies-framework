# Product terminology

Keep API and historical template IDs stable. Improve visible labels without
renaming stored records or silently changing a study's design.

## Project name

**StudyLoop** is the project and framework. **PHOENIX** remains the researcher
platform and **TERN** remains the participant extension for VS Code. Use
StudyLoop when referring to the whole project; use the component name when
describing its specific interface or responsibility.

The project rename does not change extension IDs, `tern.*` settings, protocol
fields, event sources, storage keys or release filenames. Existing studies
and participant links continue to use the same integration contracts.

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
| Evidence map | Versioned study/source relations; not the executable protocol |
| Source review | A curator's declared assessment of a passage and applicability |
| Context confirmation | Researcher checks source fit; not an independent literature review |
| Replay | Ordered captured events; never a reconstruction of missing code |
| Abstention | Explicitly declining an uncertain recommendation; not provider success |

UI actions say **Create participant links**, not “mint”. Link counts do not
claim that people have joined or completed sessions. Plan distinguishes accepted
decision previews from the current protocol used in Run. Assignment remains
deterministic; counterbalancing does not establish random allocation.

Regression coverage: `protocol/tests/test_assignment.py`,
`middleware/tests/test_authz.py`, `middleware/tests/test_terminology.py`, and the
browser rehearsals described in [planner methods](planner.md). Checks keep
registry IDs aligned with filenames, design-family names aligned with the
protocol enum, historical editor-source aliases compatible, and enrollment
actions honest. No stored identifier or schema/data migration is required.
