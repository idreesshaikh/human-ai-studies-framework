/**
 * Pairing gives a participant an enrollment condition, but a within-subject
 * study can assign a different condition to each session. At session start,
 * the refreshed server block is authoritative for the session being opened.
 */
export function conditionForSessionBlock(
  enrollmentCondition: string,
  block?: { condition?: string },
): string {
  return block?.condition?.trim() || enrollmentCondition;
}
