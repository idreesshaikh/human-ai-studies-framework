import { test, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { CompositeSink, HttpSink, JsonlSink } from '../src/vscode/sinks';
import { EventSink, StudyEvent } from '../src/core/types';

function makeEvent(seq: number, type = 'tick'): StudyEvent {
  return {
    v: 2,
    ts: new Date(0).toISOString(),
    mono: seq,
    sessionId: 's',
    participantId: 'P',
    condition: 'unspecified',
    seq,
    type,
    payload: {},
  };
}

const tempDirs: string[] = [];
function tempFile(name: string): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cog-overlay-'));
  tempDirs.push(dir);
  return path.join(dir, name);
}

afterEach(() => {
  while (tempDirs.length) {
    fs.rmSync(tempDirs.pop()!, { recursive: true, force: true });
  }
});

test('JsonlSink writes one parseable JSON object per line', async () => {
  const file = tempFile('session.jsonl');
  const sink = new JsonlSink(file);
  sink.write(makeEvent(0, 'session_start'));
  sink.write(makeEvent(1, 'fatigue_response'));
  await sink.flush();

  const lines = fs
    .readFileSync(file, 'utf8')
    .split('\n')
    .filter((l) => l.trim());
  assert.equal(lines.length, 2);
  assert.equal(JSON.parse(lines[0]).type, 'session_start');
  assert.equal(JSON.parse(lines[1]).seq, 1);
  sink.dispose();
});

test('JsonlSink creates missing parent directories', async () => {
  const file = tempFile(path.join('nested', 'deep', 'data.jsonl'));
  const sink = new JsonlSink(file);
  sink.write(makeEvent(0));
  await sink.flush();
  assert.ok(fs.existsSync(file));
  sink.dispose();
});

test('lastSeqIn returns the final seq of an existing file', async () => {
  const file = tempFile('seq.jsonl');
  const sink = new JsonlSink(file);
  for (let i = 0; i < 5; i++) sink.write(makeEvent(i));
  await sink.flush();
  sink.dispose();
  assert.equal(JsonlSink.lastSeqIn(file), 4);
});

test('lastSeqIn returns -1 for a missing file', () => {
  assert.equal(JsonlSink.lastSeqIn(tempFile('does-not-exist.jsonl')), -1);
});

test('lastSeqIn walks back past a torn final line from a crash mid-write', () => {
  const file = tempFile('torn.jsonl');
  fs.writeFileSync(
    file,
    JSON.stringify(makeEvent(7)) + '\n' + '{"seq":8,"type":"tru',
  );
  assert.equal(JsonlSink.lastSeqIn(file), 7);
});

test('crash recovery separates a torn tail from the first resumed event', async () => {
  const file = tempFile('resume-torn.jsonl');
  const before = JSON.stringify(makeEvent(7)) + '\n' + '{"seq":8,"type":"tru';
  fs.writeFileSync(file, before);
  const nextSeq = JsonlSink.lastSeqIn(file) + 1;
  const sink = new JsonlSink(file);
  try {
    sink.write(makeEvent(nextSeq, 'session_resumed'));
    await sink.flush();
    const contents = fs.readFileSync(file, 'utf8');
    assert.ok(contents.startsWith(before), 'existing evidence is preserved');
    const lastLine = contents.trimEnd().split('\n').at(-1)!;
    assert.deepEqual(JSON.parse(lastLine), makeEvent(8, 'session_resumed'));
    assert.equal(JsonlSink.lastSeqIn(file), 8);
  } finally {
    sink.dispose();
  }
});

test('reopening a complete JSONL record without a newline keeps both records', async () => {
  const file = tempFile('resume-complete.jsonl');
  fs.writeFileSync(file, JSON.stringify(makeEvent(7)));
  const sink = new JsonlSink(file);
  try {
    sink.write(makeEvent(8));
    await sink.flush();
    assert.deepEqual(
      fs
        .readFileSync(file, 'utf8')
        .trimEnd()
        .split('\n')
        .map((l) => JSON.parse(l)),
      [makeEvent(7), makeEvent(8)],
    );
  } finally {
    sink.dispose();
  }
});

test('CompositeSink fans every write out to all sinks', () => {
  const a = new RecordingSink();
  const b = new RecordingSink();
  const composite = new CompositeSink([a, b]);
  composite.write(makeEvent(0));
  assert.equal(a.writes.length, 1);
  assert.equal(b.writes.length, 1);
});

test('CompositeSink isolates one sink throwing from the others', () => {
  const good = new RecordingSink();
  const bad: EventSink = {
    write() {
      throw new Error('boom');
    },
    async flush() {},
    dispose() {},
  };
  const composite = new CompositeSink([bad, good]);
  assert.doesNotThrow(() => composite.write(makeEvent(0)));
  assert.equal(good.writes.length, 1, 'healthy sink still received the event');
});

test('CompositeSink flush and dispose reach every sink', async () => {
  const a = new RecordingSink();
  const b = new RecordingSink();
  const composite = new CompositeSink([a, b]);
  await composite.flush();
  composite.dispose();
  assert.equal(a.flushed, 1);
  assert.equal(b.flushed, 1);
  assert.ok(a.disposed && b.disposed);
});

test('CompositeSink flush isolates synchronous and asynchronous failures', async () => {
  const good = new RecordingSink();
  const synchronous: EventSink = {
    write() {},
    flush() {
      throw new Error('synchronous failure');
    },
    dispose() {},
  };
  const asynchronous: EventSink = {
    write() {},
    async flush() {
      throw new Error('asynchronous failure');
    },
    dispose() {},
  };
  await assert.doesNotReject(
    new CompositeSink([synchronous, asynchronous, good]).flush(),
  );
  assert.equal(good.flushed, 1);
});

test('HttpSink attaches the session credential as a bearer when set', async () => {
  const seen: Record<string, string> = {};
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (_url: string, init: RequestInit) => {
    Object.assign(seen, init.headers as Record<string, string>);
    return { ok: true, status: 200 } as Response;
  }) as typeof fetch;
  const sink = new HttpSink('http://x/ingest/events', 100_000, 'cred-xyz');
  try {
    sink.write(makeEvent(0, 'session_start'));
    await sink.flush();
    assert.equal(seen['authorization'], 'Bearer cred-xyz');
  } finally {
    sink.dispose();
    globalThis.fetch = originalFetch;
  }
});

test('HttpSink omits the authorization header when no credential is set', async () => {
  const seen: Record<string, string> = {};
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (_url: string, init: RequestInit) => {
    Object.assign(seen, init.headers as Record<string, string>);
    return { ok: true, status: 200 } as Response;
  }) as typeof fetch;
  const sink = new HttpSink('http://x/ingest/events', 100_000);
  try {
    sink.write(makeEvent(0, 'session_start'));
    await sink.flush();
    assert.equal(Object.hasOwn(seen, 'authorization'), false);
  } finally {
    sink.dispose();
    globalThis.fetch = originalFetch;
  }
});

class RecordingSink implements EventSink {
  readonly writes: StudyEvent[] = [];
  flushed = 0;
  disposed = false;
  write(event: StudyEvent): void {
    this.writes.push(event);
  }
  async flush(): Promise<void> {
    this.flushed++;
  }
  dispose(): void {
    this.disposed = true;
  }
}

test('HttpSink tracks pending count and last successful send time', async () => {
  const realFetch = globalThis.fetch;
  let ok = false;
  globalThis.fetch = (async () => ({ ok })) as unknown as typeof fetch;
  const sink = new HttpSink('http://x.test/ingest', 3_600_000);
  try {
    sink.write(makeEvent(0));
    assert.equal(sink.pendingCount, 1);
    assert.equal(sink.lastSuccessAt, undefined);
    await sink.flush();
    assert.equal(sink.pendingCount, 1, 'failed send stays pending');
    assert.equal(sink.lastSuccessAt, undefined);
    ok = true;
    await sink.flush();
    assert.equal(sink.pendingCount, 0);
    assert.equal(typeof sink.lastSuccessAt, 'number');
  } finally {
    globalThis.fetch = realFetch;
    sink.dispose();
  }
});

test('HttpSink counts an in-flight batch as pending until the server accepts it', async (t) => {
  let accept!: (response: Response) => void;
  t.mock.method(
    globalThis,
    'fetch',
    () =>
      new Promise<Response>((resolve) => {
        accept = resolve;
      }),
  );
  const sink = new HttpSink('http://x.test/ingest', 3_600_000);
  try {
    sink.write(makeEvent(0));
    const sending = sink.flush();
    assert.equal(sink.pendingCount, 1);
    assert.equal(sink.deliveredCount, 0);
    accept(new Response(null, { status: 204 }));
    await sending;
    assert.equal(sink.pendingCount, 0);
    assert.equal(sink.deliveredCount, 1);
  } finally {
    accept?.(new Response(null, { status: 204 }));
    sink.dispose();
  }
});

test('HttpSink flush waits for an active request and sends events queued meanwhile', async (t) => {
  let accept!: (response: Response) => void;
  const batches: number[][] = [];
  t.mock.method(globalThis, 'fetch', (_url: unknown, init: RequestInit) => {
    const body = JSON.parse(init.body as string) as { events: StudyEvent[] };
    batches.push(body.events.map((event) => event.seq));
    return batches.length === 1
      ? new Promise<Response>((resolve) => {
          accept = resolve;
        })
      : Promise.resolve(new Response(null, { status: 204 }));
  });
  const sink = new HttpSink('http://x.test/ingest', 3_600_000);
  try {
    sink.write(makeEvent(0));
    const sending = sink.flush();
    sink.write(makeEvent(1, 'session_end'));
    let completed = false;
    const finalFlush = sink.flush().then(() => {
      completed = true;
    });
    await Promise.resolve();
    assert.equal(completed, false, 'final flush must await server acceptance');
    accept(new Response(null, { status: 204 }));
    await Promise.all([sending, finalFlush]);
    assert.deepEqual(batches, [[0], [1]]);
    assert.equal(sink.pendingCount, 0);
    assert.equal(sink.deliveredCount, 2);
  } finally {
    accept?.(new Response(null, { status: 204 }));
    sink.dispose();
  }
});

test('HttpSink retries a failed batch before newer events', async (t) => {
  const batches: number[][] = [];
  t.mock.method(
    globalThis,
    'fetch',
    async (_url: unknown, init: RequestInit) => {
      const body = JSON.parse(init.body as string) as { events: StudyEvent[] };
      batches.push(body.events.map((event) => event.seq));
      return new Response(null, { status: batches.length === 1 ? 503 : 204 });
    },
  );
  const sink = new HttpSink('http://x.test/ingest', 3_600_000);
  try {
    sink.write(makeEvent(0));
    await sink.flush();
    sink.write(makeEvent(1));
    await sink.flush();
    assert.deepEqual(batches, [[0], [0, 1]]);
    assert.equal(sink.deliveredCount, 2);
  } finally {
    sink.dispose();
  }
});

test('HttpSink bounds the outage queue and retains the newest events', async (t) => {
  const batches: number[][] = [];
  t.mock.method(
    globalThis,
    'fetch',
    async (_url: unknown, init: RequestInit) => {
      const body = JSON.parse(init.body as string) as { events: StudyEvent[] };
      batches.push(body.events.map((event) => event.seq));
      return new Response(null, { status: batches.length === 1 ? 503 : 204 });
    },
  );
  const sink = new HttpSink('http://x.test/ingest', 3_600_000);
  try {
    for (let i = 0; i < 2_500; i++) sink.write(makeEvent(i));
    assert.equal(sink.pendingCount, 2_000);
    await sink.flush();
    for (let i = 2_500; i < 3_000; i++) sink.write(makeEvent(i));
    await sink.flush();
    assert.equal(batches[0].length, 2_000);
    assert.equal(batches[0][0], 500);
    assert.equal(batches[1].length, 2_000);
    assert.equal(batches[1][0], 1_000);
    assert.equal(batches[1].at(-1), 2_999);
    assert.equal(sink.pendingCount, 0);
  } finally {
    sink.dispose();
  }
});

test('HttpSink aborts a hung request and allows the next retry', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  let requests = 0;
  t.mock.method(globalThis, 'fetch', (_url: unknown, init: RequestInit) => {
    requests++;
    if (requests > 1)
      return Promise.resolve(new Response(null, { status: 204 }));
    return new Promise<Response>((_resolve, reject) => {
      init.signal!.addEventListener(
        'abort',
        () => reject(new Error('aborted')),
        { once: true },
      );
    });
  });
  const sink = new HttpSink('http://x.test/ingest', 3_600_000);
  try {
    sink.write(makeEvent(0));
    const sending = sink.flush();
    t.mock.timers.tick(4_000);
    await sending;
    assert.equal(sink.pendingCount, 1);
    assert.equal(sink.deliveredCount, 0);
    await sink.flush();
    assert.equal(sink.pendingCount, 0);
    assert.equal(sink.deliveredCount, 1);
  } finally {
    sink.dispose();
  }
});
