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
