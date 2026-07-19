# User flows

## 1. S7's journey — arrival to running study (FR-PLAT-4, FR-CONV, FR-TPL-3)

```mermaid
flowchart TD
    classDef hero fill:#fbcfe8,stroke:#db2777,color:#831843
    classDef conv fill:#c7d2fe,stroke:#4f46e5,color:#312e81
    classDef branch fill:#fde68a,stroke:#d97706,color:#78350f
    classDef run fill:#bbf7d0,stroke:#16a34a,color:#14532d

    A["Hero page<br/>(live demo 1 click; ≤3 interactions to a real report)"]:::hero
    B["Sign up (Clerk) → create/join project<br/>roles: owner · researcher · viewer"]:::hero
    C["Open design conversation<br/>'what do you want to know?'"]:::conv
    D["Idea → grounded design moves<br/>papers matched & recommended in-thread"]:::conv
    E{"Does the dataset exist?<br/>(FR-TPL-3 branch)"}:::branch
    F["LIVE PATH<br/>template configures 4 instrument legs;<br/>extension install + derived settings"]:::run
    G["CURATED PATH<br/>sampling frame → GitHub mining job →<br/>normalizer → validity-threats record"]:::run
    H["Compile → diff → approve<br/>protocol = document of record"]:::conv
    I["Lifecycle gates: ethics → pilot → collect"]:::run
    J["Recipes run the prescribed statistics<br/>honest per-RQ report, beautiful figures"]:::run
    K["Paper draft + replication kit out<br/>conversation = elicitation record"]:::run

    A --> B --> C --> D --> E
    E -->|no| F
    E -->|yes| G
    F --> H
    G --> H
    H --> I --> J --> K
    D -.->|papers → study list<br/>RAG scope grows| D
```

## 2. The literature-review loop (FR-LIT-9/10) — "it becomes easy"

```mermaid
flowchart LR
    classDef s fill:#c7d2fe,stroke:#4f46e5,color:#312e81
    A["Describe idea<br/>(or paste an abstract)"]:::s
    B["Matched papers arrive<br/>tier badge + match reason"]:::s
    C["Add to list<br/>(one click)"]:::s
    D["Constellation grows<br/>clusters form by theme"]:::s
    E["Select & ask<br/>scoped RAG: methods, stats,<br/>validation guidance — all cited"]:::s
    F["Gaps surface<br/>'no paper here measures X'<br/>→ becomes an RQ candidate"]:::s
    A --> B --> C --> D --> E --> F -->|feeds back| A
```

## 3. No-LLM degradation path (FR-CONV §5, FR-TPL-3 rev 2)

```mermaid
flowchart TD
    A{"LLM key configured?"}
    A -->|yes| B["Conversation-first designer"]
    A -->|no| C["Structured designer only<br/>(template picker, parameter grid,<br/>slot-completeness meter)"]
    B --> D["Same protocol draft"]
    C --> D
    D --> E["Same validation, gates,<br/>recipes, reports"]
    C -.->|FTS-only matching<br/>still works| C
```

The platform is **fully usable with zero external services**: matching
degrades to FTS relevance, the designer to the structured form, the
graph to cached edges — nothing load-bearing is cloud-owned (NFR-4/5/7).
