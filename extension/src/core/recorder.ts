import { EventSink, SCHEMA_VERSION, StudyCondition, StudyEvent } from './types';

export interface SessionMeta {
  sessionId: string;
  participantId: string;
  condition: StudyCondition;
}

/**
 * Stamps every event with session metadata, wall-clock + monotonic
 * timestamps, and a monotonic sequence number, then hands it to the sink(s).
 * This is the single choke point through which all study data flows.
 *
 * A sink throwing must never break the participant's session - data capture
 * is subordinate to not disturbing the study. Failures are counted and
 * reported through `onSinkError` (once), and the event is still returned so
 * callers can proceed.
 */
export class Recorder {
  private seq: number;
  private readonly monoBase: number;
  private sinkErrors = 0;

  constructor(
    private readonly sink: EventSink,
    private readonly meta: SessionMeta,
    opts?: {
      /** Continue numbering after a crash-resume (last persisted seq + 1). */
      startSeq?: number;
      /** Monotonic ms already elapsed before this recorder was (re)created. */
      monoOffsetMs?: number;
      onSinkError?: (error: unknown, totalErrors: number) => void;
    },
  ) {
    this.seq = opts?.startSeq ?? 0;
    this.monoBase = Recorder.monoNow() - (opts?.monoOffsetMs ?? 0);
    this.onSinkError = opts?.onSinkError;
  }

  private readonly onSinkError?: (error: unknown, totalErrors: number) => void;

  /** High-resolution monotonic clock, independent of the system clock. */
  static monoNow(): number {
    // globalThis.performance exists in Node >= 16 and in browsers.
    return typeof performance !== 'undefined' ? performance.now() : Date.now();
  }

  get nextSeq(): number {
    return this.seq;
  }

  record(type: string, payload: Record<string, unknown> = {}): StudyEvent {
    const event: StudyEvent = {
      v: SCHEMA_VERSION,
      ts: new Date().toISOString(),
      mono: Math.round(Recorder.monoNow() - this.monoBase),
      sessionId: this.meta.sessionId,
      participantId: this.meta.participantId,
      condition: this.meta.condition,
      seq: this.seq++,
      type,
      payload,
    };
    try {
      this.sink.write(event);
    } catch (err) {
      this.sinkErrors++;
      this.onSinkError?.(err, this.sinkErrors);
    }
    return event;
  }

  async flush(): Promise<void> {
    try {
      await this.sink.flush();
    } catch (err) {
      this.sinkErrors++;
      this.onSinkError?.(err, this.sinkErrors);
    }
  }
}
