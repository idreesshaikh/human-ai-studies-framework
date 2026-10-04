/**
 * Fetch the researcher's uploaded study folder and unpack it once.
 *
 * Portable core: `fetch` is injected, so the download, integrity and reuse
 * rules are checkable without a server. The adapter turns any failure into the
 * participant-facing fallback.
 */
import * as fs from 'node:fs';
import * as nodePath from 'node:path';
import { sha256Hex, unzipTo } from './unzip';

export class WorkspaceFetchError extends Error {}

const READY = '.tern-unpacked';
/** Matches the middleware's upload cap; refuse anything bigger before hashing. */
export const MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024;

export interface ArchiveRequest {
  /** The study server, e.g. `https://study.example`. */
  serverUrl: string;
  /** The archive path the server named, relative to `serverUrl`. */
  url: string;
  credential: string;
  sha256: string;
  size: number;
  /** Where unpacked folders live; one subfolder per archive hash. */
  destRoot: string;
  fetchFn?: typeof fetch;
}

/** Download, verify and unpack; returns the folder to open. A zip with one
 *  top-level folder opens that folder, so the participant lands in the task. */
export async function fetchAndUnpack(req: ArchiveRequest): Promise<string> {
  const dest = nodePath.join(req.destRoot, req.sha256.slice(0, 16));
  if (!fs.existsSync(nodePath.join(dest, READY))) {
    if (req.size > MAX_DOWNLOAD_BYTES) {
      throw new WorkspaceFetchError('the study folder is too large');
    }
    const doFetch = req.fetchFn ?? fetch;
    let res: Response;
    try {
      res = await doFetch(new URL(req.url, req.serverUrl).toString(), {
        headers: { authorization: `Bearer ${req.credential}` },
      });
    } catch {
      throw new WorkspaceFetchError('the study server could not be reached');
    }
    if (!res.ok) {
      throw new WorkspaceFetchError(`the study server said ${res.status}`);
    }
    const data = Buffer.from(await res.arrayBuffer());
    if (data.length !== req.size || sha256Hex(data) !== req.sha256) {
      throw new WorkspaceFetchError(
        'the downloaded folder did not match what the researcher uploaded',
      );
    }
    fs.rmSync(dest, { recursive: true, force: true });
    const staging = `${dest}.part`;
    fs.rmSync(staging, { recursive: true, force: true });
    unzipTo(data, staging);
    fs.writeFileSync(nodePath.join(staging, READY), '');
    fs.renameSync(staging, dest);
  }
  const entries = fs.readdirSync(dest).filter((n) => n !== READY);
  if (
    entries.length === 1 &&
    fs.statSync(nodePath.join(dest, entries[0])).isDirectory()
  ) {
    return nodePath.join(dest, entries[0]);
  }
  return dest;
}
