/**
 * Which study folder a paired link should open, and what to do when it can't.
 *
 * Portable core: pure decisions over the assigned block and the window we are
 * in. The adapter (`vscode/pairing.ts`) does the opening, downloading and
 * messaging, so every launch path is checkable here without VS Code.
 */
import * as nodePath from 'node:path';
import { fileURLToPath } from 'node:url';
import type { SessionBlock, WorkspaceSpec } from './captureConfig';

export interface WorkspaceEnv {
  /** VS Code for the web has no file system to open a folder from. Remote
   *  windows (WSL, SSH, containers) are fine: the existence check and any
   *  unpacking run on the extension host, the same place the folder opens. */
  web: boolean;
  homeDir: string;
  /** The folder already open in this window, if any. */
  currentFolder?: string;
}

export type WorkspaceTarget =
  | { kind: 'none' }
  | { kind: 'open'; folder: string }
  | { kind: 'already-open'; folder: string }
  | {
      kind: 'download';
      url: string;
      sha256: string;
      size: number;
      filename: string;
    }
  | { kind: 'fallback'; reason: string; shown: string };

/** What the server asked for: its explicit setting, else the task's materials. */
export function workspaceSpec(block: SessionBlock): WorkspaceSpec | undefined {
  if (block.workspace) return block.workspace;
  const materials = block.materials.trim();
  return materials ? { kind: 'path', path: materials } : undefined;
}

export const WEB_REASON =
  "VS Code for the web has no local file system, so the study folder can't be opened here. Open the study from desktop VS Code.";

export function resolveWorkspaceTarget(
  block: SessionBlock,
  env: WorkspaceEnv,
): WorkspaceTarget {
  const spec = workspaceSpec(block);
  if (!spec) return { kind: 'none' };
  const shown = spec.kind === 'path' ? spec.path.trim() : spec.filename;
  if (env.web) return { kind: 'fallback', reason: WEB_REASON, shown };

  if (spec.kind === 'archive') {
    return {
      kind: 'download',
      url: spec.url,
      sha256: spec.sha256,
      size: spec.size,
      filename: spec.filename,
    };
  }

  const raw = spec.path.trim();
  if (/^https?:\/\//i.test(raw)) {
    return {
      kind: 'fallback',
      reason:
        'The study folder is a web address. TERN never clones or downloads repositories for you; get the folder from your researcher and open it yourself.',
      shown: raw,
    };
  }
  let folder: string;
  if (raw.startsWith('file://')) {
    try {
      folder = fileURLToPath(raw);
    } catch {
      return {
        kind: 'fallback',
        reason: 'The study folder address is not a valid file:// URI.',
        shown: raw,
      };
    }
  } else if (raw === '~' || raw.startsWith('~/')) {
    folder = nodePath.join(env.homeDir, raw.slice(1));
  } else if (nodePath.isAbsolute(raw)) {
    folder = raw;
  } else {
    return {
      kind: 'fallback',
      reason:
        'The study folder is not an absolute path, so TERN cannot tell where it is.',
      shown: raw,
    };
  }
  folder = nodePath.resolve(folder);
  if (env.currentFolder && nodePath.resolve(env.currentFolder) === folder) {
    return { kind: 'already-open', folder };
  }
  return { kind: 'open', folder };
}
