# ai-cognitive-load-rehearsal: data dictionary

## Data dictionary

Every column in the exported dataset, one row each. A payload key is documented only if events of that type actually appear in the data.

| Column | Type | Meaning |
| --- | --- | --- |
| `sessionId` | str | the session this row belongs to; joins the timeline |
| `taskId` | str | the protocol task assigned to this session |
| `participantId` | str | anonymized participant id (P01, P02, ...) |
| `condition` | str | the condition this session ran under |
| `ts` | datetime64[us, UTC] | UTC timestamp (ISO-8601, millisecond precision) |
| `type` | str | event type  -  what the row records |
| `seq` | int64 | per-session sequence number on the producer's stream |
| `flags` | object | integrity flags the middleware stamped on ingest (empty = clean) |
| `schemaVersion` | int | producer row schema version |
| `metricId` | str | stable metric-row identity used for idempotent replay |
| `payload.chars` | any | payload key on agent_turn events |
| `payload.latencyMs` | any | payload key on agent_turn events |
| `payload.responseChars` | any | payload key on agent_turn events |
| `payload.role` | any | payload key on agent_turn events |
| `payload.turnIndex` | any | payload key on agent_turn events |
| `payload.action` | any | payload key on ai_suggestion events |
| `payload.suggestionId` | any | payload key on ai_suggestion events |
| `payload.cursorMs` | any | payload key on attention events |
| `payload.edited` | any | payload key on attention events |
| `payload.endLine` | any | payload key on attention events |
| `payload.exitReason` | any | payload key on attention events |
| `payload.file` | any | payload key on attention events |
| `payload.focusMs` | any | payload key on attention events |
| `payload.hoverMs` | any | payload key on attention events |
| `payload.mode` | any | payload key on attention events |
| `payload.startLine` | any | payload key on attention events |
| `payload.charCount` | any | payload key on clipboard_paste events |
| `payload.lineCount` | any | payload key on clipboard_paste events |
| `payload.targetFile` | any | payload key on clipboard_paste events |
| `payload.charsAdded` | any | payload key on edit_burst events |
| `payload.charsDeleted` | any | payload key on edit_burst events |
| `payload.durationMs` | any | payload key on edit_burst events |
| `payload.file` | any | payload key on edit_burst events |
| `payload.linesTouched` | any | payload key on edit_burst events |
| `payload.origin` | any | payload key on edit_burst events |
| `payload.file` | any | payload key on editor_focus events |
| `payload.groupCount` | any | payload key on editor_focus events |
| `payload.languageId` | any | payload key on editor_focus events |
| `payload.state` | any | payload key on editor_focus events |
| `payload.effort` | any | payload key on end_survey events |
| `payload.frustration` | any | payload key on end_survey events |
| `payload.mentalDemand` | any | payload key on end_survey events |
| `payload.comments` | any | payload key on end_survey_response events |
| `payload.msToComplete` | any | payload key on end_survey_response events |
| `payload.responses` | any | payload key on end_survey_response events |
| `payload.captureConfigVersion` | any | payload key on environment_snapshot events |
| `payload.extensionVersions` | any | payload key on environment_snapshot events |
| `payload.os` | any | payload key on environment_snapshot events |
| `payload.taskId` | any | payload key on environment_snapshot events |
| `payload.vscodeVersion` | any | payload key on environment_snapshot events |
| `payload.deferralMs` | any | payload key on fatigue_prompt_shown events |
| `payload.trigger` | any | payload key on fatigue_prompt_shown events |
| `payload.cancelled` | any | payload key on fatigue_response events |
| `payload.deferralMs` | any | payload key on fatigue_response events |
| `payload.minutesIntoSession` | any | payload key on fatigue_response events |
| `payload.msToAnswer` | any | payload key on fatigue_response events |
| `payload.points` | any | payload key on fatigue_response events |
| `payload.scaleId` | any | payload key on fatigue_response events |
| `payload.score` | any | payload key on fatigue_response events |
| `payload.skipped` | any | payload key on fatigue_response events |
| `payload.trigger` | any | payload key on fatigue_response events |
| `payload.value` | any | payload key on fatigue_response events |
| `payload.charCount` | any | payload key on file_save events |
| `payload.file` | any | payload key on file_save events |
| `payload.lineCount` | any | payload key on file_save events |
| `payload.state` | any | payload key on heartbeat events |
| `payload.lagMs` | any | payload key on post_prompt_resumption events |
| `payload.promptType` | any | payload key on post_prompt_resumption events |
| `payload.reason` | any | payload key on session_end events |
| `payload.extensionVersion` | any | payload key on session_start events |
| `payload.fatigueIntervalMin` | any | payload key on session_start events |
| `payload.fatigueJitterPercent` | any | payload key on session_start events |
| `payload.ide` | any | payload key on session_start events |
| `payload.ideVersion` | any | payload key on session_start events |
| `payload.plannedDurationMin` | any | payload key on session_start events |
| `payload.platform` | any | payload key on session_start events |
| `payload.workspace` | any | payload key on session_start events |
| `payload.actualDurationMs` | any | payload key on session_timer_ended events |
| `payload.pausedMs` | any | payload key on session_timer_ended events |
| `payload.reason` | any | payload key on session_timer_ended events |
| `payload.endLine` | any | payload key on stuck_detected events |
| `payload.evidenceMs` | any | payload key on stuck_detected events |
| `payload.file` | any | payload key on stuck_detected events |
| `payload.reason` | any | payload key on stuck_detected events |
| `payload.startLine` | any | payload key on stuck_detected events |
| `payload.answer` | any | payload key on stuck_response events |
| `payload.evidenceMs` | any | payload key on stuck_response events |
| `payload.msToAnswer` | any | payload key on stuck_response events |
| `payload.region` | any | payload key on stuck_response events |
| `payload.firstGreenMs` | any | payload key on task_outcome events |
| `payload.passed` | any | payload key on task_outcome events |
| `payload.bottomLine` | any | payload key on visible_range events |
| `payload.file` | any | payload key on visible_range events |
| `payload.topLine` | any | payload key on visible_range events |
| `payload.totalLines` | any | payload key on visible_range events |
| `payload.minutesIntoSession` | any | payload key on window_blur events |
| `payload.awayMs` | any | payload key on window_focus events |
| `payload.minutesIntoSession` | any | payload key on window_focus events |
