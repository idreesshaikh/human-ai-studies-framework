import * as fs from 'fs';
import * as path from 'path';
import { EventSink, StudyEvent } from '../core/types';

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

export class HttpSink implements EventSink {
  private buffer: StudyEvent[] = [];
  private timer: ReturnType<typeof setInterval>;
  private inFlight = false;
  private consecutiveFailures = 0;

  private delivered = 0;
  private static readonly MAX_BUFFER = 2000;
  private static readonly REQUEST_TIMEOUT_MS = 4_000;

  constructor(
    private readonly endpoint: string,
    flushIntervalMs = 5_000,
    private readonly credential?: string,
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
        const headers: Record<string, string> = {
          'content-type': 'application/json',
        };
        if (this.credential)
          headers['authorization'] = `Bearer ${this.credential}`;
        const res = await fetch(this.endpoint, {
          method: 'POST',
          headers,
          body: JSON.stringify({ source: 'tern', events: batch }),
          signal: ctrl.signal,
        });
        if (!res.ok) throw new Error(`middleware responded ${res.status}`);
        this.consecutiveFailures = 0;
        this.delivered += batch.length;
      } finally {
        clearTimeout(timeout);
      }
    } catch {
      this.consecutiveFailures++;

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

  get deliveredCount(): number {
    return this.delivered;
  }
}

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
