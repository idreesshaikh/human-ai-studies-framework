/**
 * A small, defensive zip reader for the study folder a researcher uploads.
 *
 * Node has no zip support and the extension ships no runtime dependencies, so
 * this reads the central directory itself (stored and deflate entries only; no
 * zip64, encryption or symlinks) and refuses anything that could write outside
 * the destination or balloon past the size limits.
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as nodePath from 'node:path';
import * as zlib from 'node:zlib';

export class UnzipError extends Error {}

export interface UnzipLimits {
  maxEntries: number;
  maxBytes: number;
}

export const DEFAULT_LIMITS: UnzipLimits = {
  maxEntries: 5000,
  maxBytes: 200 * 1024 * 1024,
};

interface Entry {
  name: string;
  method: number;
  compressedSize: number;
  size: number;
  localOffset: number;
  isDir: boolean;
}

export function sha256Hex(data: Uint8Array): string {
  return crypto.createHash('sha256').update(data).digest('hex');
}

function readEntries(buf: Buffer): Entry[] {
  const minEocd = 22;
  let eocd = -1;
  for (
    let i = buf.length - minEocd;
    i >= Math.max(0, buf.length - minEocd - 0xffff);
    i--
  ) {
    if (buf.readUInt32LE(i) === 0x06054b50) {
      eocd = i;
      break;
    }
  }
  if (eocd < 0) throw new UnzipError('not a zip file');
  const count = buf.readUInt16LE(eocd + 10);
  const cdOffset = buf.readUInt32LE(eocd + 16);
  if (count === 0xffff || cdOffset === 0xffffffff) {
    throw new UnzipError('zip64 archives are not supported');
  }
  const entries: Entry[] = [];
  let p = cdOffset;
  for (let n = 0; n < count; n++) {
    if (p + 46 > buf.length || buf.readUInt32LE(p) !== 0x02014b50) {
      throw new UnzipError('corrupt zip directory');
    }
    const flags = buf.readUInt16LE(p + 8);
    const method = buf.readUInt16LE(p + 10);
    const compressedSize = buf.readUInt32LE(p + 20);
    const size = buf.readUInt32LE(p + 24);
    const nameLen = buf.readUInt16LE(p + 28);
    const extraLen = buf.readUInt16LE(p + 30);
    const commentLen = buf.readUInt16LE(p + 32);
    const attr = buf.readUInt32LE(p + 38);
    const localOffset = buf.readUInt32LE(p + 42);
    const name = buf.toString('utf8', p + 46, p + 46 + nameLen);
    if (flags & 1) throw new UnzipError(`encrypted entry: ${name}`);
    if (((attr >>> 16) & 0o170000) === 0o120000) {
      throw new UnzipError(`symbolic link in zip: ${name}`);
    }
    entries.push({
      name,
      method,
      compressedSize,
      size,
      localOffset,
      isDir: name.endsWith('/'),
    });
    p += 46 + nameLen + extraLen + commentLen;
  }
  return entries;
}

function safeTarget(dest: string, name: string): string {
  const parts = name.split(/[\\/]/);
  if (
    name.startsWith('/') ||
    name.startsWith('\\') ||
    /^[A-Za-z]:/.test(name) ||
    parts.includes('..')
  ) {
    throw new UnzipError(`unsafe path in zip: ${name}`);
  }
  const target = nodePath.resolve(dest, ...parts);
  if (target !== dest && !target.startsWith(dest + nodePath.sep)) {
    throw new UnzipError(`unsafe path in zip: ${name}`);
  }
  return target;
}

/** Unpack `buf` into `dest` (created if needed). Returns the top-level names. */
export function unzipTo(
  buf: Buffer,
  dest: string,
  limits: UnzipLimits = DEFAULT_LIMITS,
): string[] {
  const entries = readEntries(buf);
  if (entries.length > limits.maxEntries) {
    throw new UnzipError('zip has too many entries');
  }
  let total = 0;
  for (const e of entries) total += e.size;
  if (total > limits.maxBytes) throw new UnzipError('zip is too large');
  const root = nodePath.resolve(dest);
  const top = new Set<string>();
  fs.mkdirSync(root, { recursive: true });
  for (const e of entries) {
    const target = safeTarget(root, e.name);
    top.add(e.name.split(/[\\/]/)[0]);
    if (e.isDir) {
      fs.mkdirSync(target, { recursive: true });
      continue;
    }
    const p = e.localOffset;
    if (p + 30 > buf.length || buf.readUInt32LE(p) !== 0x04034b50) {
      throw new UnzipError(`corrupt entry: ${e.name}`);
    }
    const start = p + 30 + buf.readUInt16LE(p + 26) + buf.readUInt16LE(p + 28);
    const raw = buf.subarray(start, start + e.compressedSize);
    let data: Buffer;
    if (e.method === 0) data = raw;
    else if (e.method === 8) {
      try {
        data = zlib.inflateRawSync(raw, { maxOutputLength: e.size });
      } catch {
        throw new UnzipError(`corrupt or oversized entry: ${e.name}`);
      }
    } else throw new UnzipError(`unsupported compression in ${e.name}`);
    if (data.length !== e.size) {
      throw new UnzipError(`size mismatch in ${e.name}`);
    }
    fs.mkdirSync(nodePath.dirname(target), { recursive: true });
    fs.writeFileSync(target, data);
  }
  return [...top];
}
