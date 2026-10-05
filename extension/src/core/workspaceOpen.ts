/**
 * The whole "open the assigned study folder" flow, with the editor behind a
 * small host interface so each launch path and failure can be tested without
 * VS Code. The adapter (`vscode/pairing.ts`) supplies the real host.
 */
import type { SessionBlock } from './captureConfig';
import {
  WorkspaceEnv,
  WorkspaceTarget,
  resolveWorkspaceTarget,
} from './workspaceTarget';

export type DownloadTarget = Extract<WorkspaceTarget, { kind: 'download' }>;

export interface WorkspaceHost {
  env: WorkspaceEnv;
  isDirectory(folder: string): boolean;
  /** Fetch and unpack an uploaded folder; resolves to the folder to open. */
  download(target: DownloadTarget): Promise<string>;
  openFolder(folder: string): Promise<void>;
  /** Tell the participant why the folder was not opened and let them recover. */
  offerFallback(reason: string, shown: string): Promise<void>;
}

export type OpenOutcome = 'none' | 'already-open' | 'opened' | 'fallback';

export async function openStudyFolder(
  block: SessionBlock,
  host: WorkspaceHost,
): Promise<OpenOutcome> {
  const target = resolveWorkspaceTarget(block, host.env);
  if (target.kind === 'none' || target.kind === 'already-open') {
    return target.kind;
  }
  if (target.kind === 'fallback') {
    await host.offerFallback(target.reason, target.shown);
    return 'fallback';
  }
  let folder: string;
  if (target.kind === 'download') {
    try {
      folder = await host.download(target);
    } catch (e) {
      await host.offerFallback(
        `The study folder could not be downloaded: ${(e as Error).message}.`,
        target.filename,
      );
      return 'fallback';
    }
  } else {
    folder = target.folder;
    if (!host.isDirectory(folder)) {
      await host.offerFallback(
        "That folder doesn't exist on this computer.",
        folder,
      );
      return 'fallback';
    }
  }
  try {
    await host.openFolder(folder);
  } catch {
    await host.offerFallback(
      'VS Code could not open the study folder.',
      folder,
    );
    return 'fallback';
  }
  return 'opened';
}
