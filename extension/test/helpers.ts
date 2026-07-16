import { mock } from 'node:test';

/** A large, realistic epoch base so `lastPromptAt = 0` sentinels in the
 *  detectors read as "long ago" the way they do against the real wall clock. */
export const CLOCK_BASE = 1_700_000_000_000;

/**
 * Advance the mocked clock to an absolute `Date.now()` target in 1 s steps,
 * mirroring the production 1 s tick cadence so interval callbacks observe the
 * same incremental time they would in a real session.
 */
export function advanceTo(target: number): void {
  while (Date.now() < target) {
    const step = Math.min(1_000, target - Date.now());
    mock.timers.tick(step);
  }
}
