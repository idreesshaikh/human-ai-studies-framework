/* The study folder participants' minted links open. Pure helpers shared by the
 * mint dialog and `scripts/verify-workspace-setting.mjs`; no browser APIs. */

export type StudyWorkspace =
  | { kind: null }
  | { kind: "path"; path: string; updatedAt: string }
  | {
      kind: "archive";
      filename: string;
      sha256: string;
      size: number;
      updatedAt: string;
    };

/** Mirrors the server's `workspace.validate_path`, so a bad path is caught
 *  before the round trip. The server stays the authority. */
export function workspacePathProblem(raw: string): string | null {
  const value = raw.trim();
  if (!value) return "Enter the folder's path on participants' computers.";
  if (/^https?:\/\//i.test(value) || /\.(zip|tar|tgz|tar\.gz)$/i.test(value)) {
    return "That is a web address or archive, not a folder path. Upload a zip of the folder instead.";
  }
  const absolute =
    value.startsWith("/") ||
    value.startsWith("~/") ||
    value.startsWith("file://") ||
    /^[A-Za-z]:[\\/]/.test(value);
  if (!absolute) {
    return "Use an absolute path (/home/…, C:\\…), ~/…, or a file:// address.";
  }
  if (value.split(/[\\/]/).includes("..")) return "The path may not contain '..'.";
  return null;
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

/** What a minted link will open, in one line for the researcher. */
export function describeWorkspace(w: StudyWorkspace): string {
  if (w.kind === "path") return `Opens ${w.path} on each participant's computer`;
  if (w.kind === "archive") {
    return `Downloads ${w.filename} (${formatBytes(w.size)}) and opens it`;
  }
  return "No study folder set: participants connect, but nothing opens for them";
}

export const WORKSPACE_ZIP_LIMIT_BYTES = 50 * 1024 * 1024;

/** A problem with a chosen file before upload, or null. */
export function workspaceFileProblem(file: {
  name: string;
  size: number;
}): string | null {
  if (!/\.zip$/i.test(file.name)) return "Choose a .zip of the study folder.";
  if (file.size > WORKSPACE_ZIP_LIMIT_BYTES) {
    return `The zip is larger than ${formatBytes(WORKSPACE_ZIP_LIMIT_BYTES)}.`;
  }
  return null;
}
