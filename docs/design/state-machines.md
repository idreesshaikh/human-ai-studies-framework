# State machines

## 1. Study lifecycle (FR-PROT-3 — v1, unchanged; v2 adds the amendment loop)

```mermaid
stateDiagram-v2
    [*] --> design
    design --> ethics : design gates ✓
    ethics --> pilot : approval artifact ✓
    pilot --> recruitment : pilot gates ✓
    recruitment --> data_collection : consent artifacts ✓
    data_collection --> analysis : planned sessions ✓
    analysis --> write_up : recipes ✓
    write_up --> [*] : paper draft + replication kit

    state data_collection {
        [*] --> collecting
        collecting --> amendment_pending : consent-relevant amendment (FR-CONV-4)
        amendment_pending --> collecting : re-approval artifact ✓
        note right of amendment_pending
            new sessions blocked;
            running sessions untouched (NFR-1);
            protocolVersion incremented
        end note
    }
```

## 2. Design move (FR-CONV-1/3)

```mermaid
stateDiagram-v2
    [*] --> proposed : platform turn carries move
    proposed --> accepted : researcher accepts
    proposed --> rejected : researcher rejects
    proposed --> superseded : newer move targets same slot
    accepted --> compiled : compilation approved & applied
    accepted --> bounced : validation failure (returns as platform turn)
    bounced --> proposed : platform re-proposes corrected move
    rejected --> [*]
    superseded --> [*]
    compiled --> [*] : hunk traceable to this move forever

    note right of compiled
        terminal & immutable —
        the elicitation record (FR-CONV-6)
        never unmakes a decision
    end note
```

## 3. Mining job (FR-CUR-2)

```mermaid
stateDiagram-v2
    [*] --> declared : sampling frame in protocol
    declared --> running : start (refuses without frame)
    running --> paused_rate_limited : GitHub 403/429 (visible, plain-language)
    paused_rate_limited --> running : backoff elapsed
    running --> interrupted : crash / stop
    interrupted --> running : resume from cursor (no duplicates, F2.1)
    running --> gated : fetch complete
    gated --> complete : validity-threats record written (F3.2)
    gated --> failed_gate : record missing → analysis gate blocks
    complete --> [*] : events normalized, joined timeline
```

## 4. Corpus entry (FR-LIT-8)

```mermaid
stateDiagram-v2
    [*] --> candidate : mentioned by a Tier-A seed (ref/citation)
    candidate --> dropped_unverifiable : no DOI/arXiv id
    candidate --> dropped_gate : citation floor / age rule
    candidate --> tier_B : gate ✓ + ranked into target
    tier_B --> refreshed : re-harvest (score/cites update)
    refreshed --> tier_B
    tier_B --> study_set : researcher adds via match (FR-LIT-9)
    study_set --> [*] : grounds conversations + scoped RAG
    dropped_unverifiable --> [*]
    dropped_gate --> [*]

    note right of tier_B
        provenance kept forever:
        score, via-seeds, s2PaperId —
        every entry independently checkable
    end note
```

## 5. Conversation turn streaming (FR-CONV-1, NFR-12)

```mermaid
stateDiagram-v2
    [*] --> composing : researcher typing (never network-blocked)
    composing --> sent
    sent --> streaming : SSE first token < 1s else progress affordance
    streaming --> settled : stream complete, moves fold into cards
    streaming --> failed : provider error
    failed --> sent : retry (input never lost)
    settled --> [*]
```
