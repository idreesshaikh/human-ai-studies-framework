# Stakeholder analysis

Seven stakeholder roles. Goals become research questions and requirements;
conflicts become documented trade-offs with a decided resolution.

## S1 - Researcher / Facilitator (primary; Idrees)

Designs and conducts the study. **Goals:** spend time on research content,
not setup; know at any moment which phase the study is in and what is
missing; trust that no session data is silently lost; get from raw data to
RQ-organized results without hand-written glue scripts.

## S2 - Participant

A developer volunteering ~45–90 minutes. **Goals:** not be interrupted or
surveilled beyond what was consented to; understand exactly what is
collected; be unidentifiable in any output. **Concern:** IDE telemetry can
capture proprietary or embarrassing content - collection must be visibly
bounded (aggregates and hashes, never raw code or keystrokes).

## S3 - Ethics board

Approves the study before data collection. **Goals:** consent, data
minimization, anonymization, and secure storage demonstrably in place;
the approved protocol is the protocol actually executed (no silent drift).
The lifecycle gate mechanism exists chiefly for S3: approval is an artifact
the platform checks, and protocol changes after approval are version-visible.

## S4 - Thesis examiner

*(Rev 2, 2026-07-17: reframed - RE is a subject the supervisor teaches
and values, not the grading rubric; the project is assessed as a
research-platform thesis.)* Assesses the built platform and its
evidence. **Goals:** a working end-to-end platform; engineering
decisions that are traceable and defensible; honest statistics behind
every claim. The structured record in this directory serves those goals
- RE practice appears where it earns its keep (the elicitation record,
the protocol as machine-readable spec), never as a performance.

## S5 - Replicating researcher

A future third party rerunning or extending the study. **Goals:** obtain the
frozen protocol, schema versions, recipes, and anonymized dataset as one
package; rerun the analysis and get the same report; swap in their own
participants without reverse-engineering anything.

## S6 - Platform developer / maintainer

Whoever extends the platform (including future Idrees, and JetBrains-port
authors). **Goals:** IDE-agnostic core stays IDE-agnostic; schemas are
versioned so old data never becomes unreadable; new instruments and recipes
plug in without touching existing legs.

## S7 - Adopting researcher (industry or academia)

A researcher who is *not* the maintainer, arriving at the hosted platform to
run their own study. **Goals:** understand within minutes what the platform
does (hero page, live demo); sign up and create a project without reading a
thesis; invite colleagues with appropriate roles; design a study by picking
a published, citable design rather than reinventing methodology; be told the
statistically correct analysis rather than having to derive it; get data
either from live instrumented sessions or from curated external sources
(GitHub, archives) through one flow. **Concern:** most "research platforms"
are task boards in disguise - S7 stays only if the platform encodes real
methodological knowledge (the paper corpus in `docs/papers/`) and saves them
from the statistics they fear getting wrong.

## Conflicts and resolutions

| # | Conflict                                                                 | Resolution                                                                                          |
| - | ------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------- |
| C1 | S1 wants rich behavioral data ↔ S2/S3 want minimal collection           | Collect aggregates and salted hashes only (FR-ETH-2); per-signal toggles owned by the protocol, so the consent form and the collection provably match. |
| C2 | S1 wants live monitoring ↔ S2 must never be interrupted                 | All live views are middleware-side; instruments never block or steal focus (NFR-1). Mirroring is best-effort; local JSONL is the source of truth (NFR-2). |
| C3 | S5 wants raw data ↔ S3 wants minimization                               | Replication kits ship the anonymized dataset only; raw session files stay with S1 under the retention policy in the protocol. |
| C4 | S6 wants general schemas ↔ S1 needs the pilot shipped                   | Generality by design, not implementation: versioned schemas and plugin contracts (NFR-4), but only the agent–human vertical slice is built (SRS Won't rows). |
