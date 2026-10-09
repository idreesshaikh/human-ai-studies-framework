// INSTRUCTOR REFERENCE SOLUTION. Never publish this file to students.
const fs = require('node:fs');
const path = require('node:path');

const CONTENT_DIR = path.join(__dirname, '..', 'content');

function handleRequest(request) {
  const req = parseRequest(request);
  if (!req) return buildResponse(400, 'Bad Request');
  if (req.method !== 'GET') return buildResponse(405, 'Method Not Allowed');
  const body = readContentFile(req.path);
  if (body === null) return buildResponse(404, 'Not Found');
  return buildResponse(200, 'OK', body);
}

function parseRequest(request) {
  if (typeof request !== 'string') return null;

  // Lines are separated by \n or \r\n. Remove any trailing \r.
  const lines = request.split('\n').map((line) => (line.endsWith('\r') ? line.slice(0, -1) : line));

  // Request line looks like: GET /index.html HTTP/1.1
  const parts = lines[0].split(' ');
  if (parts.length !== 3) return null;
  const [method, urlPath, version] = parts;
  if (method === '' || !urlPath.startsWith('/') || !version.startsWith('HTTP/')) return null;

  // Headers look like "Name: value" and end at the first empty line.
  const headers = {};
  for (const line of lines.slice(1)) {
    if (line === '') break;
    const colon = line.indexOf(':');
    if (colon === -1) continue;
    const name = line.slice(0, colon).trim().toLowerCase();
    headers[name] = line.slice(colon + 1).trim();
  }

  return { method, path: urlPath, version, headers };
}

function buildResponse(status, reason, body) {
  const head = `HTTP/1.1 ${status} ${reason}\n`;
  if (body === undefined) return head + '\n';
  return `${head}Content-Length: ${Buffer.byteLength(body)}\n\n${body}`;
}

function readContentFile(urlPath) {
  const full = path.join(CONTENT_DIR, path.normalize(urlPath));
  if (!full.startsWith(CONTENT_DIR + path.sep)) return null;
  try {
    return fs.readFileSync(full, 'utf8');
  } catch {
    return null;
  }
}

module.exports = { handleRequest, parseRequest, buildResponse, readContentFile, CONTENT_DIR };
