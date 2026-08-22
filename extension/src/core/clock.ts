/** Stable display helpers for the participant-facing study countdown. */

/**
 * Return the number of whole seconds still remaining.
 *
 * A countdown uses ceiling rather than rounding: 1.2 seconds remaining is
 * still visibly 2 seconds, and the display reaches 0 only when the clock does.
 */
export function remainingSeconds(remainingMs: number): number {
  return Math.ceil(Math.max(0, remainingMs) / 1000);
}

export function formatRemaining(remainingMs: number): string {
  const total = remainingSeconds(remainingMs);
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}
