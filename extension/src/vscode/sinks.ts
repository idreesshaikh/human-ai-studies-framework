import * as fs from 'fs';
import * as path from 'path';
import { EventSink, StudyEvent } from '../core/types';

/**
 * Append-only JSON Lines file - the local source of truth for a session.
 *
 * Robustness properties:
 *  - Stream 'error' events are captured instead of crashing the extension
 *    host (an unhandled 'error' on a WriteStream is a process-level throw).
 *  - Writes after a stream failure fall back to synchronous appends, so a
 *    transient stream error does not lose the rest of the session.
 *  - `flush()` resolves when the OS has accepted all buffered writes.
 */
export class JsonlSink implements EventSink {
  private stream?: fs.WriteStream;
  private streamBroken = false;
  readonly filePath: string;

  constructor(
    filePath: string,
    private readonly onError?: (err: unknown) => void,
  ) {
    this.filePath = filePath;
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    this.stream = this.openStream();
  }

  private openStream(): fs.WriteStream {
    const s = fs.createWriteStream(this.filePath, { flags: 'a' });
    s.on('error', (err) => {
      this.streamBroken = true;
      this.onError?.(err);
    });
    return s;
  }

  write(event: StudyEvent): void {
    const line = JSON.stringify(event) + '\n';
    if (this.stream && !this.streamBroken) {
      this.stream.write(line);
      return;
    }
    // Degraded mode: the stream died - append synchronously so the study
    // data survives even if performance suffers slightly.
    try {
      fs.appendFileSync(this.filePath, line);
    } catch (err) {
      this.onError?.(err);
    }
  }

  flush(): Promise<void> {
    if (!this.stream || this.streamBroken) return Promise.resolve();
    return new Promise((resolve) => this.stream!.write('', () => resolve()));
  }

  dispose(): void {
    this.stream?.end();
    this.stream = undefined;
  }

  /**
   * Read the last event's `seq` from an existing JSONL file, for continuing
   * a crash-interrupted session without renumbering. Returns -1 for a
   * missing/empty/corrupt file (caller starts at 0).
   */
  static lastSeqIn(filePath: string): number {
    try {
      const text = fs.readFileSync(filePath, 'utf8');
      const lines = text.split('\n').filter((l) => l.trim().length > 0);
      for (let i = lines.length - 1; i >= 0; i--) {
        try {
          const parsed = JSON.parse(lines[i]) as { seq?: number };
          if (typeof parsed.seq === 'number') return parsed.seq;
        } catch {
          // Torn final line from a crash mid-write - walk one line back.
        }
      }
      return -1;
    } catch {
      return -1;
    }
  }
}

/**
 * Fire-and-forget batching POST to the team's Python middleware
 * (ActivityWatch-style decoupling: the IDE stays lag-free; the daemon
 * aggregates). The JSONL file is always the source of truth - this sink is
 * best-effort mirroring, so its failure policy is "never disturb, never
 * grow unbounded":
 *  - requests time out (a hung server cannot pile up pending promises),
 *  - non-2xx responses count as failures and the batch is retried,
 *  - the retry buffer is capped, dropping the OLDEST events beyond the cap
 *    (the newest events are the ones a live platform cares about; the old
 *    ones are already safe in the JSONL file).
 */
export class HttpSink implements EventSink {
  private buffer: StudyEvent[] = [];
  private timer: ReturnType<typeof setInterval>;
  private inFlight = false;
  private consecutiveFailures = 0;
  private static readonly MAX_BUFFER = 2000;
  private static readonly REQUEST_TIMEOUT_MS = 4_000;

  constructor(
    private readonly endpoint: string,
    flushIntervalMs = 5_000,
  ) {
    this.timer = setInterval(() => void this.flush(), flushIntervalMs);
  }

  write(event: StudyEvent): void {
    this.buffer.push(event);
    if (this.buffer.length > HttpSink.MAX_BUFFER) {
      this.buffer.splice(0, this.buffer.length - HttpSink.MAX_BUFFER);
    }
  }

  async flush(): Promise<void> {
    if (!this.buffer.length || this.inFlight) return;
    // Simple backoff: after repeated failures, only try every 4th interval.
    if (this.consecutiveFailures >= 3 && this.consecutiveFailures % 4 !== 3) {
      this.consecutiveFailures++;
      return;
    }
    this.inFlight = true;
    const batch = this.buffer.splice(0, this.buffer.length);
    try {
      const ctrl = new AbortController();
      const timeout = setTimeout(
        () => ctrl.abort(),
        HttpSink.REQUEST_TIMEOUT_MS,
      );
      try {
        const res = await fetch(this.endpoint, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ source: 'cognitive-overlay', events: batch }),
          signal: ctrl.signal,
        });
        if (!res.ok) throw new Error(`middleware responded ${res.status}`);
        this.consecutiveFailures = 0;
      } finally {
        clearTimeout(timeout);
      }
    } catch {
      this.consecutiveFailures++;
      // Put the batch back (in front of anything written meanwhile).
      this.buffer.unshift(...batch);
      if (this.buffer.length > HttpSink.MAX_BUFFER) {
        this.buffer.splice(0, this.buffer.length - HttpSink.MAX_BUFFER);
      }
    } finally {
      this.inFlight = false;
    }
  }

  dispose(): void {
    clearInterval(this.timer);
    void this.flush();
  }
}

/** Fans writes out to several sinks (JSONL + HTTP). One sink failing never
 *  affects the others. */
export class CompositeSink implements EventSink {
  constructor(private readonly sinks: EventSink[]) {}

  write(event: StudyEvent): void {
    for (const s of this.sinks) {
      try {
        s.write(event);
      } catch {
        // Individual sink errors are surfaced by the sinks themselves.
      }
    }
  }

  async flush(): Promise<void> {
    await Promise.allSettled(this.sinks.map((s) => s.flush()));
  }

  dispose(): void {
    for (const s of this.sinks) {
      try {
        s.dispose();
      } catch {
        // Never let one sink's teardown block another's.
      }
    }
  }
}
