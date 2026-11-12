export interface FatiguePromptResult {
  value: number | null;
  skipped: boolean;
  /** Programmatic dismissal, such as pausing the study. */
  cancelled: boolean;
}

export interface FatiguePromptContext {
  paused: boolean;
  statusMenuInterrupted: boolean;
  ending: boolean;
}

/**
 * Only an explicit dismissal while the study is active counts as a skip.
 * Pausing or replacing the QuickPick with the session menu leaves the probe
 * pending for one replay after the interruption.
 */
export function shouldRetryFatiguePrompt(
  result: FatiguePromptResult,
  context: FatiguePromptContext,
): boolean {
  return (
    !context.ending &&
    (context.paused || context.statusMenuInterrupted || result.cancelled)
  );
}
