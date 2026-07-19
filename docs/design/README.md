# Design tree (living documents)

System design for the conversational research platform. Every diagram
traces to requirement IDs (`requirements/srs.md` + `requirements/specs/`);
where a diagram and a requirement disagree, the requirement wins and the
drift is a logged defect (FR-META-1). Diagrams are Mermaid (render in
GitHub, IDEs, and the platform's own docs surfaces).

| Document | Contents | Primary IDs |
| --- | --- | --- |
| `architecture.md` | C4 context + container views, deployment topology | FR-PLAT, FR-ING, FR-CONV, D34 |
| `data-model.md` | UML class diagram: projects → conversations → moves → protocol; corpus tiers; curated datasets | FR-PLAT-1, FR-CONV, FR-LIT-8, FR-CUR |
| `sequences.md` | Sequence diagrams: design-move lifecycle, paper matching, corpus harvest, amendment flow, talk-to-your-papers RAG | FR-CONV-1/3/4, FR-LIT-8/9/10 |
| `state-machines.md` | Study lifecycle, design-move states, mining-job states, corpus-entry states | FR-PROT-3, FR-CONV, FR-CUR-2, FR-LIT-8 |
| `flows.md` | S7 journey, dataset-exists branch, literature-review loop | FR-PLAT-4, FR-TPL-3, FR-LIT-9/10 |
| `ui-motion-spec.md` | The quirky-precise UI: component inventory, micro-interaction timings, the living literature constellation, streaming choreography | NFR-12, FR-LIT-10, D34/D35 |

Reading order for newcomers: `flows.md` → `architecture.md` →
`sequences.md`; implementers add `data-model.md` + `state-machines.md`;
design work starts at `ui-motion-spec.md`.
