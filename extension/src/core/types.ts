/**
 * Portable core types - no IDE imports allowed anywhere under src/core.
 * An IDE adapter (src/vscode, later src/jetbrains, ...) maps its native
 * editor events onto these types and renders the prompts the core requests.
 */

export type StudyCondition = 'ai-assisted' | 'unassisted' | 'unspecified';

/**
 * Bump when the event shape or the meaning of a payload field changes, so
 * analysis scripts can branch on it instead of guessing from file dates.
 *
 * v3: behavioral telemetry leg - adds editor_focus, visible_range,
 * edit_burst, clipboard_paste, ai_suggestion, file_save, heartbeat, and
 * environment_snapshot event types (see src/core/behavior.ts). Also carries
 * the additive `attention` event (region-level time-on-code, see
 * src/core/attention.ts).
 * v4: comprehension probe leg - adds comprehension_probe_response event type
 * carrying chunkReference, promptKind, answer, correct, msToAnswer, expired
 * (Phase 21, extension/src/core/comprehensionProbe.ts).
 */
export const SCHEMA_VERSION = 4;

/** One row of the study dataset. Serialized as JSON Lines. */
export interface StudyEvent {
  /** Event schema version (see SCHEMA_VERSION). */
  v: number;
  /** ISO-8601 wall-clock timestamp with millisecond precision. */
  ts: string;
  /**
   * Monotonic milliseconds since session start. Immune to NTP jumps and
   * manual clock changes - use `ts` to join with the other study legs and
   * `mono` for within-session durations and ordering sanity checks.
   */
  mono: number;
  sessionId: string;
  participantId: string;
  condition: StudyCondition;
  taskId?: string;
  /** Monotonic per-session sequence number, for ordering & gap detection. */
  seq: number;
  /** Event type, e.g. 'session_start', 'fatigue_response', 'stuck_response'. */
  type: string;
  payload: Record<string, unknown>;
}

/** Where events go. Adapters provide JSONL-file and HTTP implementations. */
export interface EventSink {
  write(event: StudyEvent): void;
  flush(): Promise<void>;
  dispose(): void;
}

/**
 * Everything needed to resurrect a session after an IDE crash or window
 * reload. Persisted by the adapter at session start and on every material
 * state change; deleted on clean end.
 */
export interface SessionSnapshot {
  schemaVersion: number;
  sessionId: string;
  participantId: string;
  condition: StudyCondition;
  /** Epoch ms when the session originally started. */
  startedAtEpochMs: number;
  plannedDurationMs: number;
  fatigueIntervalMs: number;
  /** Accumulated paused time so far (excluded from the study clock). */
  pausedMsAccumulated: number;
  dataFile: string;
}

/**
 * Normalized editor signal. The adapter translates native IDE events
 * (selection change, scroll, document edit, window focus) into these.
 * Lines are 0-based.
 */
export interface EditorSignal {
  kind: 'edit' | 'selection' | 'scroll' | 'focus' | 'blur';
  /** Stable file identifier (fsPath / URI string). */
  file?: string;
  /** Cursor line for 'selection', midpoint of visible range for 'scroll'. */
  line?: number;
  topLine?: number;
  bottomLine?: number;
  /** Epoch milliseconds. */
  at: number;
}

export type StuckReason = 'dwell' | 'scroll-thrash';

/** A code region the detector believes the participant is stuck on. */
export interface StuckRegion {
  file: string;
  startLine: number;
  endLine: number;
  reason: StuckReason;
  /** How long (ms) the pattern persisted before triggering. */
  evidenceMs: number;
}

export type StuckAnswer = 'yes' | 'no' | 'hint' | 'dismissed' | 'timeout';

export interface Disposable {
  dispose(): void;
}
