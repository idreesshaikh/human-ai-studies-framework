# pilot-2026  -  data dictionary

## Data dictionary

Every column in the exported dataset, one row each. A payload key is documented only if events of that type actually appear in the data.

| Column | Type | Meaning |
| --- | --- | --- |
| `source` | str | producer stream (tern, agent-capture, task-harness, metrics, ...) |
| `ts` | datetime64[us, UTC] | UTC timestamp (ISO-8601, millisecond precision) |
| `sessionId` | str | the session this row belongs to; joins the timeline |
| `participantId` | str | anonymized participant id (P01, P02, ...) |
| `condition` | str | the condition this session ran under |
| `taskId` | str | the protocol task assigned to this session |
| `schemaVersion` | int64 | producer row schema version |
| `type` | str | event type  -  what the row records |
| `seq` | int64 | per-session sequence number on the producer's stream |
| `flags` | object | integrity flags the middleware stamped on ingest (empty = clean) |
| `payload.chars` | any | payload key on agent_turn events |
| `payload.latencyMs` | any | payload key on agent_turn events |
| `payload.responseChars` | any | payload key on agent_turn events |
| `payload.role` | any | payload key on agent_turn events |
| `payload.synthetic` | bool | simulated agent_turn event; not participant data |
| `payload.turnIndex` | any | payload key on agent_turn events |
| `payload.action` | any | payload key on ai_suggestion events |
| `payload.charCount` | any | payload key on ai_suggestion events |
| `payload.synthetic` | bool | simulated ai_suggestion event; not participant data |
| `payload.visibleMs` | any | payload key on ai_suggestion events |
| `payload.charCount` | any | payload key on clipboard_paste events |
| `payload.synthetic` | bool | simulated clipboard_paste event; not participant data |
| `payload.file` | any | payload key on editor_focus events |
| `payload.synthetic` | bool | simulated editor_focus event; not participant data |
| `payload.effort` | any | payload key on end_survey events |
| `payload.frustration` | any | payload key on end_survey events |
| `payload.mentalDemand` | any | payload key on end_survey events |
| `payload.synthetic` | bool | simulated end_survey event; not participant data |
| `payload.score` | any | payload key on fatigue_response events |
| `payload.synthetic` | bool | simulated fatigue_response event; not participant data |
| `payload.evidenceMs` | any | payload key on stuck_response events |
| `payload.synthetic` | bool | simulated stuck_response event; not participant data |
| `payload.firstGreenMs` | any | payload key on task_outcome events |
| `payload.passed` | any | payload key on task_outcome events |
| `payload.synthetic` | bool | simulated task_outcome event; not participant data |
| `synthetic` | bool | simulated metric row; not participant data |
| `calls` | numeric | static code metric over the workspace |
| `lines` | numeric | static code metric over the workspace |
| `nesting_penalty` | numeric | static code metric over the workspace |
