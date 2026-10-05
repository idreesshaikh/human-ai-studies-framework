import { test } from 'node:test';
import assert from 'node:assert/strict';
import type { SessionBlock, WorkspaceSpec } from '../src/core/captureConfig';
import {
  WEB_REASON,
  WorkspaceEnv,
  resolveWorkspaceTarget,
  workspaceSpec,
} from '../src/core/workspaceTarget';

const LOCAL: WorkspaceEnv = { web: false, homeDir: '/home/p1' };
const WEB: WorkspaceEnv = { web: true, homeDir: '/home/p1' };
const SHA = 'a'.repeat(64);

function block(over: Partial<SessionBlock> = {}): SessionBlock {
  return {
    index: 0,
    of: 1,
    taskId: 't1',
    condition: 'ai-assisted',
    title: 'Fix the bug',
    description: '',
    materials: '',
    ...over,
  };
}
const path = (p: string): WorkspaceSpec => ({ kind: 'path', path: p });
const archive: WorkspaceSpec = {
  kind: 'archive',
  url: '/studies/s/workspace/archive',
  sha256: SHA,
  size: 10,
  filename: 'task.zip',
};

test('no folder anywhere means nothing to open', () => {
  assert.deepEqual(resolveWorkspaceTarget(block(), LOCAL), { kind: 'none' });
});

test('the researcher setting wins over the task materials', () => {
  const b = block({ materials: '/old', workspace: path('/new') });
  assert.deepEqual(workspaceSpec(b), path('/new'));
  assert.deepEqual(resolveWorkspaceTarget(b, LOCAL), {
    kind: 'open',
    folder: '/new',
  });
});

test('materials alone still works for older servers', () => {
  assert.deepEqual(
    resolveWorkspaceTarget(block({ materials: '/home/p1/task' }), LOCAL),
    {
      kind: 'open',
      folder: '/home/p1/task',
    },
  );
});

for (const [raw, folder] of [
  ['/home/p1/task', '/home/p1/task'],
  ['file:///home/p1/task', '/home/p1/task'],
  ['~/task', '/home/p1/task'],
  ['/home/p1/task/../task', '/home/p1/task'],
] as const) {
  test(`local window opens ${raw}`, () => {
    assert.deepEqual(
      resolveWorkspaceTarget(block({ workspace: path(raw) }), LOCAL),
      {
        kind: 'open',
        folder,
      },
    );
  });
}

test('a folder already open is not reopened', () => {
  const env = { ...LOCAL, currentFolder: '/home/p1/task' };
  assert.deepEqual(
    resolveWorkspaceTarget(block({ workspace: path('~/task') }), env),
    {
      kind: 'already-open',
      folder: '/home/p1/task',
    },
  );
});

for (const [raw, why] of [
  ['relative/dir', /not an absolute path/],
  ['https://github.com/o/r', /never clones/],
  ['file://bad host/x', /valid file/],
] as const) {
  test(`falls back with a reason for ${raw}`, () => {
    const t = resolveWorkspaceTarget(block({ workspace: path(raw) }), LOCAL);
    assert.equal(t.kind, 'fallback');
    if (t.kind === 'fallback') {
      assert.match(t.reason, why);
      assert.equal(t.shown, raw);
    }
  });
}

test('an uploaded archive is downloaded in a local window', () => {
  assert.deepEqual(
    resolveWorkspaceTarget(block({ workspace: archive }), LOCAL),
    {
      kind: 'download',
      url: archive.url,
      sha256: SHA,
      size: 10,
      filename: 'task.zip',
    },
  );
});

test('VS Code for the web: path and archive both fall back', () => {
  for (const workspace of [path('/home/p1/task'), archive]) {
    const t = resolveWorkspaceTarget(block({ workspace }), WEB);
    assert.equal(t.kind, 'fallback');
    if (t.kind === 'fallback') assert.equal(t.reason, WEB_REASON);
  }
});

test('a WSL, SSH or container window is a normal desktop window: path and archive proceed', () => {
  // `remoteName` is deliberately not part of the environment: the folder is
  // checked and unpacked on the extension host, where it will be opened.
  assert.equal(
    resolveWorkspaceTarget(block({ workspace: path('/home/test') }), LOCAL)
      .kind,
    'open',
  );
  assert.equal(
    resolveWorkspaceTarget(block({ workspace: archive }), LOCAL).kind,
    'download',
  );
});
