# pilot-2026  -  data dictionary

## Data dictionary

Every column in the exported dataset, one row each. A payload key is documented only if events of that type actually appear in the data.

| Column | Type | Meaning |
| --- | --- | --- |
| `sessionId` | object | the session this row belongs to; joins the timeline |
| `participantId` | object | anonymized participant id (P01, P02, ...) |
| `condition` | object | the condition this session ran under |
| `ts` | object | UTC timestamp (ISO-8601, millisecond precision) |
| `type` | object | event type  -  what the row records |
| `seq` | object | per-session sequence number on the producer's stream |
| `flags` | object | integrity flags the middleware stamped on ingest (empty = clean) |
