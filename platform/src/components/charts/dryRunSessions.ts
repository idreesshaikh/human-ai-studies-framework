/* After a dry run the server reports which sessions it stored. If the status
 * refresh has not (or could not) list them, the Sessions section falls back to
 * those ids instead of claiming "No sessions yet" under a "Dry run complete"
 * banner. */
export function dryRunFallbackSessionIds(
  report: { sessionIds?: string[] } | null,
  loadedSessionCount: number,
): string[] {
  if (!report || loadedSessionCount > 0) return [];
  return report.sessionIds ?? [];
}
