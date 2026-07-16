import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Recorder, SessionMeta } from '../src/core/recorder';
import { EventSink, SCHEMA_VERSION, StudyEvent } from '../src/core/types';

const META: SessionMeta = {
  sessionId: 's-test',
  participantId: 'P01',
  condition: 'ai-assisted',
};

class CapturingSink implements EventSink {
  readonly events: StudyEvent[] = [];
  flushed = 0;
  disposed = false;
  write(event: StudyEvent): void {
    this.events.push(event);
  }
  async flush(): Promise<void> {
    this.flushed++;
  }
  dispose(): void {
    this.disposed = true;
  }
}

class ThrowingSink implements EventSink {
  write(): void {
    throw new Error('write failed');
  }
  async flush(): Promise<void> {
    throw new Error('flush failed');
  }
  dispose(): void {}
}

test('stamps every event with metadata, schema version, and an incrementing seq', () => {
  const sink = new CapturingSink();
  const rec = new Recorder(sink, META);

  const a = rec.record('session_start', { foo: 1 });
  const b = rec.record('fatigue_response', { value: 4 });

  assert.equal(a.v, SCHEMA_VERSION);
  assert.equal(a.type, 'session_start');
  assert.deepEqual(a.payload, { foo: 1 });
  assert.equal(a.sessionId, 's-test');
  assert.equal(a.participantId, 'P01');
  assert.equal(a.condition, 'ai-assisted');

  assert.equal(a.seq, 0);
  assert.equal(b.seq, 1);
  assert.equal(rec.nextSeq, 2);
  assert.equal(sink.events.length, 2);
  assert.ok(typeof a.mono === 'number' && a.mono >= 0);
  assert.ok(!Number.isNaN(Date.parse(a.ts)), 'ts is ISO-8601 parseable');
});

test('continues numbering from startSeq after a crash-resume', () => {
  const sink = new CapturingSink();
  const rec = new Recorder(sink, META, { startSeq: 42 });
  assert.equal(rec.nextSeq, 42);
  assert.equal(rec.record('session_resumed').seq, 42);
  assert.equal(rec.record('tick').seq, 43);
});

test('empty payload defaults to an object', () => {
  const rec = new Recorder(new CapturingSink(), META);
  assert.deepEqual(rec.record('bare').payload, {});
});

test('a throwing sink never breaks recording and is reported once per error', () => {
  const errors: number[] = [];
  const rec = new Recorder(new ThrowingSink(), META, {
    onSinkError: (_err, total) => errors.push(total),
  });

  const event = rec.record('session_start');
  // The event is still produced and returned to the caller.
  assert.equal(event.type, 'session_start');
  assert.equal(event.seq, 0);
  // The seq counter still advanced despite the sink failure.
  assert.equal(rec.record('next').seq, 1);
  assert.deepEqual(
    errors,
    [1, 2],
    'error callback sees a running failure count',
  );
});

test('flush failures are caught and counted', async () => {
  const errors: number[] = [];
  const rec = new Recorder(new ThrowingSink(), META, {
    onSinkError: (_err, total) => errors.push(total),
  });
  await rec.flush();
  assert.deepEqual(errors, [1]);
});

test('flush delegates to the sink when healthy', async () => {
  const sink = new CapturingSink();
  const rec = new Recorder(sink, META);
  await rec.flush();
  assert.equal(sink.flushed, 1);
});
