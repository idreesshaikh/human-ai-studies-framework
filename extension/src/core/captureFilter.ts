/**
 * Capture filter (FR-INST-12): behavioral telemetry is restricted to
 * protocol-declared languages and workspace-internal files (pilot:
 * `["python"]`, workspace only - WakaTime's language/path filter pattern,
 * decision D4). Lives in core so the predicate is unit-testable (NFR-3).
 */

export interface CaptureFilterConfig {
  /** Language IDs to capture; empty = all languages. */
  languages: string[];
  /** Capture only files inside the workspace (data minimization, S2/S3). */
  workspaceInternalOnly: boolean;
}

export interface CaptureCandidate {
  languageId: string;
  /**
   * Workspace-relative path, or undefined when the file lives outside the
   * workspace (its absolute path must never be recorded - FR-ETH-2).
   */
  workspaceRelativePath?: string;
}

export function shouldCapture(
  cfg: CaptureFilterConfig,
  file: CaptureCandidate,
): boolean {
  if (cfg.workspaceInternalOnly && file.workspaceRelativePath === undefined) {
    return false;
  }
  if (cfg.languages.length > 0 && !cfg.languages.includes(file.languageId)) {
    return false;
  }
  return true;
}
