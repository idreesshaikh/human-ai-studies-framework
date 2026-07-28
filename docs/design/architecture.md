# Architecture — system design

C4-style, two levels. Traces: FR-PLAT (shell), FR-CONV (conversation),
FR-LIT-8/9/10 (corpus + matching + living view), FR-CUR (mining),
FR-AGF (manifest), D34 (surfaces) and the instrument legs.

## Level 1 — system context

```mermaid
flowchart TB
    classDef person fill:#fde68a,stroke:#d97706,color:#78350f
    classDef sys fill:#c7d2fe,stroke:#4f46e5,color:#312e81
    classDef ext fill:#e2e8f0,stroke:#64748b,color:#334155

    S7["🧑‍🔬 Adopting researcher (S7)<br/>designs & runs studies conversationally"]:::person
    S1["🧑‍💻 Facilitator (S1)<br/>runs live sessions"]:::person
    P["🧑 Participant (S2)<br/>instrumented, never interrupted"]:::person
    AGENT["🤖 External agents<br/>drive API/UI via manifest (FR-AGF)"]:::person

    PLATFORM["🔮 Human-AI Studies Platform<br/>conversation → protocol → data → honest analysis → paper"]:::sys

    S2API["Semantic Scholar Graph API<br/>(D8/D36: metadata only)"]:::ext
    GH["GitHub API<br/>(FR-CUR-2 mining)"]:::ext
    LLM["LLM provider (D32: Mistral)<br/>REST, server-side tool loop"]:::ext
    CLERK["Clerk (D29, optional)<br/>hosted identity"]:::ext
    CC["Claude Code<br/>(D13: hooks + transcripts)"]:::ext

    S7 -->|talks study into existence| PLATFORM
    S1 -->|operates sessions| PLATFORM
    P -->|four-leg telemetry| PLATFORM
    AGENT -->|/.well-known/platform-manifest| PLATFORM
    PLATFORM -->|snowball + enrich| S2API
    PLATFORM -->|mine PRs/commits/issues| GH
    PLATFORM -->|grounded proposals, cited answers| LLM
    PLATFORM -.->|hosted mode only| CLERK
    CC -->|agent-leg events| PLATFORM
```

Boundary rules (unchanged invariants): participant data never leaves
facilitator-controlled storage (NFR-5); the LLM sees papers, templates,
drafts, aggregates — never row-level events (FR-ETH-4); every external
service is optional and degrades gracefully (NFR-4).

## Level 2 — containers

```mermaid
flowchart TB
    classDef ui fill:#fbcfe8,stroke:#db2777,color:#831843
    classDef svc fill:#c7d2fe,stroke:#4f46e5,color:#312e81
    classDef store fill:#bbf7d0,stroke:#16a34a,color:#14532d
    classDef edge fill:#fed7aa,stroke:#ea580c,color:#7c2d12

    subgraph SURFACES["Surfaces (D34)"]
        PLAT["platform/ — React 19 + shadcn/ui<br/>hero · projects · design conversation ·<br/>living literature view · review surfaces"]:::ui
    end

    subgraph MW["middleware :8000 — FastAPI (one process serves all)"]
        API["REST + SSE API<br/>auth seam (none/token/clerk)"]:::svc
        CONV["Conversation service<br/>threads · design moves · FR-CONV"]:::svc
        COMPILER["Protocol compiler<br/>deterministic moves→YAML (FR-CONV-3)"]:::svc
        MATCH["Paper matcher (FR-LIT-9)<br/>FTS relevance → LLM rerank"]:::svc
        KNOW["Knowledge service<br/>papers · graph · FTS5 RAG (FR-LIT)"]:::svc
        MINE["Mining service (FR-CUR)<br/>GitHub adapter · normalizer"]:::svc
        MANIFEST["Manifest generator (FR-AGF-1)<br/>from documents of record"]:::svc
    end

    subgraph STORES["Storage (D26: PostgreSQL on Railway, superseding D11's SQLite-only model)"]
        DB[("PostgreSQL (default)<br/>projects · studies · events ·<br/>conversations · papers · FTS<br/>SQLite fallback for script testing")]:::store
        FILES[("content-addressed file store<br/>gate artifacts · PDFs")]:::store
    end

    subgraph LEGS["Instrument legs"]
        EXT["extension/ TERN<br/>cognitive + behavioral"]:::edge
        MET["metrics/ 9-metric matrix"]:::edge
        AGC["agent-capture/ hooks + transcripts"]:::edge
    end

    HARVEST["scripts/corpus_harvest.py (FR-LIT-8)<br/>Tier-B snowball → corpus-index.json"]:::svc
    ANA["analysis/ recipes · stats · report · paper"]:::svc
    PROTO["protocol/ schema · lifecycle · derive"]:::svc

    PLAT -->|REST + SSE| API
    API --> CONV --> COMPILER --> PROTO
    CONV --> MATCH --> KNOW
    API --> MINE
    API --> MANIFEST
    CONV & KNOW & MINE --> DB
    API --> FILES
    LEGS -->|JSONL/HTTP, fire-and-forget| API
    HARVEST -->|corpus-index.json import| KNOW
    ANA --> DB
    PROTO -.->|drives| LEGS
```

Key placements, argued:

1. **The compiler lives server-side, next to the protocol package** —
   determinism (FR-CONV-3) is testable only where one implementation
   exists; the UI renders diffs, never computes them.
2. **The matcher is a service, not a UI feature** — FR-LIT-9's
   degradation ladder (FTS-only when no LLM key) must be one code path;
   both surfaces and the manifest consumers get identical matches.
3. **Harvest is a script, not a service** (D36) — corpus growth is an
   editorial batch act with a versioned gate, not a runtime behavior;
   its *output* (`corpus-index.json`) is what the platform imports.
4. **One process serves everything** (NFR-7) — the platform, conversation,
   knowledge, mining, and manifest are routers inside the one FastAPI app;
   `docker compose up` remains the whole story, SSE included.

## Deployment topology

Railway is the sole deployment target for the production service. Local
development mirrors it exactly (PostgreSQL, single container).

```mermaid
flowchart LR
    classDef host fill:#e0f2fe,stroke:#0284c7,color:#0c4a6e
    DEV["Laptop (NFR-7)<br/>docker compose up<br/>Postgres · optional SonarQube<br/>none/token auth"]:::host
    RAILWAY["Railway (D26)<br/>seeded demo · reseeds on boot<br/>managed PostgreSQL · Clerk auth<br/>TLS · custom domain"]:::host
    DEV -->|git push main| RAILWAY
```
