import { test } from 'node:test';
import assert from 'node:assert/strict';
import type { SessionBlock } from '../src/core/captureConfig';
import { WorkspaceHost, openStudyFolder } from '../src/core/workspaceOpen';

const block = (
  workspace?: SessionBlock['workspace'],
  materials = '',
): SessionBlock => ({
  index: 0,
  of: 1,
  taskId: 't',
  condition: 'c',
  title: 'T',
  description: '',
  materials,
  workspace,
});
const archive = {
  kind: 'archive' as const,
  url: '/u',
  sha256: 'c'.repeat(64),
  size: 1,
  filename: 'task.zip',
};

function host(over: Partial<WorkspaceHost> = {}) {
  const log: string[] = [];
  const h: WorkspaceHost = {
    env: { web: false, homeDir: '/home/p1' },
    isDirectory: () => true,
    download: async () => '/cache/task',
    openFolder: async (f) => void log.push(`open ${f}`),
    offerFallback: async (reason, shown) =>
      void log.push(`fallback ${reason} | ${shown}`),
    ...over,
  };
  return { h, log };
}

test('local path that exists: opens it', async () => {
  const { h, log } = host();
  assert.equal(
    await openStudyFolder(block({ kind: 'path', path: '/home/p1/task' }), h),
    'opened',
  );
  assert.deepEqual(log, ['open /home/p1/task']);
});

test('local path that is missing: clear fallback, nothing opened', async () => {
  const { h, log } = host({ isDirectory: () => false });
  assert.equal(
    await openStudyFolder(block({ kind: 'path', path: '/nope' }), h),
    'fallback',
  );
  assert.deepEqual(log, [
    "fallback That folder doesn't exist on this computer. | /nope",
  ]);
});

test('uploaded archive: downloads, then opens the unpacked folder', async () => {
  const { h, log } = host();
  assert.equal(await openStudyFolder(block(archive), h), 'opened');
  assert.deepEqual(log, ['open /cache/task']);
});

test('archive download failure: fallback names the cause and the file', async () => {
  const { h, log } = host({
    download: async () => {
      throw new Error('the study server said 404');
    },
  });
  assert.equal(await openStudyFolder(block(archive), h), 'fallback');
  assert.deepEqual(log, [
    'fallback The study folder could not be downloaded: the study server said 404. | task.zip',
  ]);
});

test('openFolder throwing: fallback instead of an unhandled error', async () => {
  const { h, log } = host({
    openFolder: async () => {
      throw new Error('boom');
    },
  });
  assert.equal(
    await openStudyFolder(block({ kind: 'path', path: '/home/p1/task' }), h),
    'fallback',
  );
  assert.match(log[0], /could not open the study folder/);
});

test('VS Code for the web: fallback, never a download or open', async () => {
  const { h, log } = host({ env: { web: true, homeDir: '/home/p1' } });
  for (const ws of [
    archive,
    { kind: 'path' as const, path: '/home/p1/task' },
  ]) {
    assert.equal(await openStudyFolder(block(ws), h), 'fallback');
  }
  assert.equal(log.filter((l) => l.startsWith('open')).length, 0);
  assert.equal(log.length, 2);
});

test('already open and no folder both do nothing', async () => {
  const open = host({
    env: { web: false, homeDir: '/h', currentFolder: '/home/p1/task' },
  });
  assert.equal(
    await openStudyFolder(
      block({ kind: 'path', path: '/home/p1/task' }),
      open.h,
    ),
    'already-open',
  );
  const none = host();
  assert.equal(await openStudyFolder(block(), none.h), 'none');
  assert.deepEqual([...open.log, ...none.log], []);
});

test('old servers: task materials alone still opens', async () => {
  const { h, log } = host();
  assert.equal(
    await openStudyFolder(block(undefined, '/home/p1/task'), h),
    'opened',
  );
  assert.deepEqual(log, ['open /home/p1/task']);
});
