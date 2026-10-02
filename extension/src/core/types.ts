export type StudyCondition = 'ai-assisted' | 'unassisted' | 'unspecified';

export const SCHEMA_VERSION = 4;

export interface StudyEvent {
  v: number;

  ts: string;

  mono: number;
  sessionId: string;
  participantId: string;
  condition: StudyCondition;
  taskId?: string;

  seq: number;

  type: string;
  payload: Record<string, unknown>;
}

export interface EventSink {
  write(event: StudyEvent): void;
  flush(): Promise<void>;
  dispose(): void;
}

export interface SessionSnapshot {
  schemaVersion: number;
  sessionId: string;
  participantId: string;
  condition: StudyCondition;

  startedAtEpochMs: number;
  plannedDurationMs: number;
  fatigueIntervalMs: number;

  pausedMsAccumulated: number;
  dataFile: string;
}

export interface EditorSignal {
  kind: 'edit' | 'selection' | 'scroll' | 'focus' | 'blur';

  file?: string;

  line?: number;
  topLine?: number;
  bottomLine?: number;

  at: number;
}

export type StuckReason = 'dwell' | 'scroll-thrash';

export interface StuckRegion {
  file: string;
  startLine: number;
  endLine: number;
  reason: StuckReason;

  evidenceMs: number;
}

export type StuckAnswer = 'yes' | 'no' | 'hint' | 'dismissed' | 'timeout';

export interface Disposable {
  dispose(): void;
}
