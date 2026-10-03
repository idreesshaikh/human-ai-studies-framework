export interface CaptureFilterConfig {
  languages: string[];

  workspaceInternalOnly: boolean;
}

export interface CaptureCandidate {
  languageId: string;

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
