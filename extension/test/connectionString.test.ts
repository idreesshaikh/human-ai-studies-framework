import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  decodeConnectionString,
  ConnectionStringError,
} from '../src/core/connectionString';

test('decodes a well-formed connection string', () => {
  const c = decodeConnectionString('https://study.lab.example#Ab3xToken');
  assert.equal(c.serverUrl, 'https://study.lab.example');
  assert.equal(c.token, 'Ab3xToken');
});

test('strips a trailing slash from the server URL', () => {
  assert.equal(
    decodeConnectionString('https://s.example/#tok').serverUrl,
    'https://s.example',
  );
});

test('rejects a string with no separator', () => {
  assert.throws(
    () => decodeConnectionString('https://s.example'),
    ConnectionStringError,
  );
});

test('rejects a non-http server URL', () => {
  assert.throws(
    () => decodeConnectionString('ftp://s.example#tok'),
    ConnectionStringError,
  );
});

test('rejects an empty token', () => {
  assert.throws(
    () => decodeConnectionString('https://s.example#'),
    ConnectionStringError,
  );
});
