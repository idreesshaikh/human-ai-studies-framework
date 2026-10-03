import { EventSink, SCHEMA_VERSION, StudyCondition, StudyEvent } from './types';

export interface SessionMeta {
  sessionId: string;
  participantId: string;
  condition: StudyCondition;
  taskId?: string;
}

export class Recorder {
  private seq: number;
  private readonly monoBase: number;
  private sinkErrors = 0;

  constructor(
    private readonly sink: EventSink,
    private readonly meta: SessionMeta,
    opts?: {
      startSeq?: number;

      monoOffsetMs?: number;
      onSinkError?: (error: unknown, totalErrors: number) => void;
    },
  ) {
    this.seq = opts?.startSeq ?? 0;
    this.monoBase = Recorder.monoNow() - (opts?.monoOffsetMs ?? 0);
    this.onSinkError = opts?.onSinkError;
  }

  private readonly onSinkError?: (error: unknown, totalErrors: number) => void;

  static monoNow(): number {
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
      taskId: this.meta.taskId ?? '',
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
