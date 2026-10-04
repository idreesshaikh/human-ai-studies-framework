import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import {
  WorkspaceFetchError,
  fetchAndUnpack,
} from '../src/core/workspaceArchive';
import { sha256Hex } from '../src/core/unzip';
import { buildZip } from './zipBuilder';

const zip = buildZip([
  { name: 'task/' },
  { name: 'task/README.md', data: 'hello' },
]);
const flat = buildZip([
  { name: 'a.txt', data: '1' },
  { name: 'b.txt', data: '2' },
]);

function req(data: Buffer, fetchFn: typeof fetch, over = {}) {
  return {
    serverUrl: 'https://study.example',
    url: '/studies/s/workspace/archive',
    credential: 'cred',
    sha256: sha256Hex(data),
    size: data.length,
    destRoot: fs.mkdtempSync(path.join(os.tmpdir(), 'tern-ws-')),
    fetchFn,
    ...over,
  };
}
const serve = (data: Buffer, calls: string[] = []): typeof fetch =>
  (async (url: string, init: RequestInit) => {
    calls.push(
      `${url} ${(init.headers as Record<string, string>).authorization}`,
    );
    return new Response(data);
  }) as unknown as typeof fetch;

test('downloads with the credential, verifies, unpacks, and opens the single top folder', async () => {
  const calls: string[] = [];
  const folder = await fetchAndUnpack(req(zip, serve(zip, calls)));
  assert.deepEqual(calls, [
    'https://study.example/studies/s/workspace/archive Bearer cred',
  ]);
  assert.equal(path.basename(folder), 'task');
  assert.equal(
    fs.readFileSync(path.join(folder, 'README.md'), 'utf8'),
    'hello',
  );
});

test('a zip with several top-level entries opens the unpacked root', async () => {
  const r = req(flat, serve(flat));
  const folder = await fetchAndUnpack(r);
  assert.equal(folder, path.join(r.destRoot, r.sha256.slice(0, 16)));
  assert.equal(fs.existsSync(path.join(folder, 'a.txt')), true);
});

test('an unpacked folder is reused without another download', async () => {
  const calls: string[] = [];
  const r = req(zip, serve(zip, calls));
  await fetchAndUnpack(r);
  await fetchAndUnpack(r);
  assert.equal(calls.length, 1);
});

test('a download that does not match the uploaded hash is refused and leaves nothing', async () => {
  const r = req(zip, serve(flat), { size: flat.length });
  await assert.rejects(() => fetchAndUnpack(r), /did not match/);
  assert.deepEqual(fs.readdirSync(r.destRoot), []);
});

test('server errors and unreachable servers become clear errors', async () => {
  const notFound = (async () =>
    new Response('', { status: 404 })) as unknown as typeof fetch;
  await assert.rejects(
    () => fetchAndUnpack(req(zip, notFound)),
    /server said 404/,
  );
  const down = (async () => {
    throw new Error('ECONNREFUSED');
  }) as unknown as typeof fetch;
  await assert.rejects(
    () => fetchAndUnpack(req(zip, down)),
    WorkspaceFetchError,
  );
});

test('an oversized folder is refused before downloading', async () => {
  const calls: string[] = [];
  await assert.rejects(
    () =>
      fetchAndUnpack(req(zip, serve(zip, calls), { size: 51 * 1024 * 1024 })),
    /too large/,
  );
  assert.equal(calls.length, 0);
});
