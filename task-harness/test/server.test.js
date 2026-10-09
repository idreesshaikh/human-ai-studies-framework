'use strict';

// Twelve checks, as in the original study. Participants can read but not edit this file.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { handleRequest } = require('../index');

const content = (p) => fs.readFileSync(path.join(__dirname, '..', 'content', p), 'utf8');
const get = (p, extra = '') => handleRequest(`GET ${p} HTTP/1.1\r\nHost: localhost\r\n${extra}\r\n`);
const ok = (body) => `HTTP/1.1 200 OK\nContent-Length: ${Buffer.byteLength(body)}\n\n${body}`;

test('1. returns 200 with the exact file contents for a valid GET', () => {
  assert.equal(get('/index.html'), ok(content('index.html')));
});

test('2. Content-Length matches the body length', () => {
  const res = get('/index.html');
  const [head, ...rest] = res.split('\n\n');
  assert.match(head, /^HTTP\/1\.1 200 OK\nContent-Length: (\d+)$/);
  assert.equal(Number(head.match(/Content-Length: (\d+)/)[1]), Buffer.byteLength(rest.join('\n\n')));
});

test('3. serves files from subdirectories', () => {
  assert.equal(get('/about/team.html'), ok(content('about/team.html')));
});

test('4. serves other file types verbatim', () => {
  assert.equal(get('/style.css'), ok(content('style.css')));
});

test('5. Content-Length counts bytes, not characters', () => {
  const body = content('unicode.html');
  assert.notEqual(Buffer.byteLength(body), body.length);
  assert.equal(get('/unicode.html'), ok(body));
});

test('6. returns 404 for a missing file', () => {
  assert.equal(get('/missing.html'), 'HTTP/1.1 404 Not Found\n\n');
});

test('7. returns 404 for a missing file in a subdirectory', () => {
  assert.equal(get('/about/nobody.html'), 'HTTP/1.1 404 Not Found\n\n');
});

test('8. returns 400 for a request that is not HTTP', () => {
  assert.equal(handleRequest('hello world'), 'HTTP/1.1 400 Bad Request\n\n');
});

test('9. returns 400 for an empty request', () => {
  assert.equal(handleRequest(''), 'HTTP/1.1 400 Bad Request\n\n');
});

test('10. returns 400 when the request line has no HTTP version', () => {
  assert.equal(handleRequest('GET /index.html\r\n\r\n'), 'HTTP/1.1 400 Bad Request\n\n');
});

test('11. returns 405 for methods other than GET', () => {
  for (const method of ['POST', 'PUT', 'DELETE', 'PATCH']) {
    assert.equal(
      handleRequest(`${method} /index.html HTTP/1.1\r\nHost: localhost\r\n\r\n`),
      'HTTP/1.1 405 Method Not Allowed\n\n',
      method,
    );
  }
});

test('12. accepts requests with many headers and ignores them', () => {
  const extra = 'User-Agent: test\r\nAccept: */*\r\nAccept-Language: en\r\nX-Custom: a: b\r\n';
  assert.equal(get('/index.html', extra), ok(content('index.html')));
});
