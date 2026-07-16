import { test } from 'node:test';
import assert from 'node:assert/strict';
import { CaptureFilterConfig, shouldCapture } from '../src/core/captureFilter';

const PILOT: CaptureFilterConfig = {
  languages: ['python'],
  workspaceInternalOnly: true,
};

test('captures a workspace python file under the pilot filter', () => {
  assert.equal(
    shouldCapture(PILOT, {
      languageId: 'python',
      workspaceRelativePath: 'src/task.py',
    }),
    true,
  );
});

test('rejects a non-declared language (non-Python edit => zero events)', () => {
  assert.equal(
    shouldCapture(PILOT, {
      languageId: 'markdown',
      workspaceRelativePath: 'README.md',
    }),
    false,
  );
});

test('rejects files outside the workspace when internal-only is set', () => {
  assert.equal(
    shouldCapture(PILOT, { languageId: 'python' }),
    false,
    'no workspace-relative path means the file lives outside the workspace',
  );
});

test('empty language list means all languages', () => {
  const cfg: CaptureFilterConfig = {
    languages: [],
    workspaceInternalOnly: true,
  };
  assert.equal(
    shouldCapture(cfg, {
      languageId: 'typescript',
      workspaceRelativePath: 'a.ts',
    }),
    true,
  );
});

test('workspaceInternalOnly=false admits external files of a declared language', () => {
  const cfg: CaptureFilterConfig = {
    languages: ['python'],
    workspaceInternalOnly: false,
  };
  assert.equal(shouldCapture(cfg, { languageId: 'python' }), true);
});
