import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { UnzipError, sha256Hex, unzipTo } from '../src/core/unzip';
import { buildZip } from './zipBuilder';

function tmp(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'tern-unzip-'));
}

for (const method of [0, 8] as const) {
  test(`unpacks a folder (method ${method}) and reports its top level`, () => {
    const dest = tmp();
    const top = unzipTo(
      buildZip(
        [
          { name: 'task/' },
          { name: 'task/README.md', data: 'hello' },
          { name: 'task/src/a.py', data: 'print(1)' },
        ],
        method,
      ),
      dest,
    );
    assert.deepEqual(top, ['task']);
    assert.equal(
      fs.readFileSync(path.join(dest, 'task/README.md'), 'utf8'),
      'hello',
    );
    assert.equal(
      fs.readFileSync(path.join(dest, 'task/src/a.py'), 'utf8'),
      'print(1)',
    );
  });
}

for (const name of [
  '../evil.txt',
  '/abs/evil.txt',
  'C:/evil.txt',
  'a/../../evil.txt',
  '..\\evil.txt',
]) {
  test(`refuses a path that escapes the folder: ${name}`, () => {
    const dest = tmp();
    assert.throws(
      () => unzipTo(buildZip([{ name, data: 'x' }]), path.join(dest, 'out')),
      /unsafe path/,
    );
    assert.equal(fs.existsSync(path.join(dest, 'evil.txt')), false);
  });
}

test('refuses symbolic links, bad input and over-limit archives', () => {
  assert.throws(
    () =>
      unzipTo(
        buildZip([{ name: 'l', data: '/etc/passwd', attr: 0o120777 * 65536 }]),
        tmp(),
      ),
    /symbolic link/,
  );
  assert.throws(
    () => unzipTo(Buffer.from('not a zip at all'), tmp()),
    UnzipError,
  );
  const two = buildZip([
    { name: 'a', data: '1' },
    { name: 'b', data: '2' },
  ]);
  assert.throws(
    () => unzipTo(two, tmp(), { maxEntries: 1, maxBytes: 1e6 }),
    /too many entries/,
  );
  assert.throws(
    () =>
      unzipTo(buildZip([{ name: 'a', data: 'x'.repeat(50) }]), tmp(), {
        maxEntries: 9,
        maxBytes: 10,
      }),
    /too large/,
  );
});

test('a zip that lies about its size is refused, not unpacked', () => {
  const zip = buildZip([
    { name: 'a.txt', data: 'x'.repeat(1000), declaredSize: 5 },
  ]);
  assert.throws(() => unzipTo(zip, tmp()), /corrupt or oversized/);
});

test('sha256Hex matches the server-side digest format', () => {
  assert.equal(
    sha256Hex(Buffer.from('abc')),
    'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
  );
});
