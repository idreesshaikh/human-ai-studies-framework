import { Disposable, StudyCondition } from './types';

export interface SessionConfig {
  participantId: string;
  condition: StudyCondition;
  durationMs: number;
  /** Mean interval between experience-sampling (fatigue) probes. */
  fatigueIntervalMs: number;
  /**
   * Randomize each probe interval by ±this fraction (0–0.9). Signal-contingent
   * jitter prevents participants from anticipating probes (a classic ESM
   * reactivity confound with fixed schedules). 0 = strictly periodic.
   */
  fatigueJitterRatio: number;
  /**
   * Never probe during the last stretch of the session - a probe answered
   * 30 s before the debrief is redundant and annoying.
   */
  fatigueQuietTailMs: number;
}

export interface SessionHooks {
  /** Time for an experience-sampling probe. The adapter renders it. */
  onFatigueDue(): void;
  /** Session over (timer elapsed or manually ended). */
  onEnded(reason: 'elapsed' | 'manual'): void;
  /** Once per second, for the status-bar countdown. */
  onTick(remainingMs: number, elapsedMs: number): void;
}

export interface SessionRestoreState {
  sessionId: string;
  startedAtEpochMs: number;
  pausedMsAccumulated: number;
}

export function newSessionId(): string {
  const rand = Math.random().toString(36).slice(2, 8);
  return `s-${Date.now().toString(36)}-${rand}`;
}

/**
 * Owns the study clock. Design constraints:
 *
 *  - SLEEP-SAFE: a laptop lid-close must not silently stretch the session.
 *    Everything is derived from wall-clock elapsed time inside a 1 s tick -
 *    there is no long-lived setTimeout that could be frozen by OS sleep.
 *  - PAUSABLE: breaks (bathroom, facilitator interruption) are excluded from
 *    the study clock and shift the probe schedule instead of eating it.
 *  - RESUMABLE: can be reconstructed after an IDE crash from a persisted
 *    snapshot; the clock continues from real elapsed time.
 *
 * Pure timers, no IDE imports.
 */
export class StudySession implements Disposable {
  readonly id: string;
  readonly startedAt: number;
  private tickTimer?: ReturnType<typeof setInterval>;
  private ended = false;
  private pausedSince?: number;
  private pausedMsTotal = 0;
  private nextFatigueAtElapsed: number;

  constructor(
    readonly cfg: SessionConfig,
    private readonly hooks: SessionHooks,
    restore?: SessionRestoreState,
    /**
     * The id for a *fresh* session, when the caller has already minted one.
     * The adapter needs the id before the session exists: it sends it with
     * the capture-config re-pull so the server can assign this session's
     * task block against it. A restored session ignores this and keeps its
     * own id — that session was already assigned.
     */
    plannedId?: string,
  ) {
    this.id = restore?.sessionId ?? plannedId ?? newSessionId();
    this.startedAt = restore?.startedAtEpochMs ?? Date.now();
    this.pausedMsTotal = restore?.pausedMsAccumulated ?? 0;
    this.nextFatigueAtElapsed = this.elapsedMs + this.jitteredInterval();
    this.tickTimer = setInterval(() => this.tick(), 1_000);
  }

  /** Active (non-paused) study time elapsed. */
  get elapsedMs(): number {
    const pausedNow = this.pausedSince ? Date.now() - this.pausedSince : 0;
    return Date.now() - this.startedAt - this.pausedMsTotal - pausedNow;
  }

  get remainingMs(): number {
    return Math.max(0, this.cfg.durationMs - this.elapsedMs);
  }

  get paused(): boolean {
    return this.pausedSince !== undefined;
  }

  get pausedMsAccumulated(): number {
    const pausedNow = this.pausedSince ? Date.now() - this.pausedSince : 0;
    return this.pausedMsTotal + pausedNow;
  }

  pause(): void {
    if (this.ended || this.pausedSince !== undefined) return;
    this.pausedSince = Date.now();
  }

  /**
   * End the current pause and return the duration (ms) of the pause that just
   * ended. Returns 0 if the session was not paused. Callers record the return
   * value as the per-pause duration; `pausedMsAccumulated` remains the total.
   */
  resume(): number {
    if (this.pausedSince === undefined) return 0;
    const thisPauseMs = Date.now() - this.pausedSince;
    this.pausedMsTotal += thisPauseMs;
    this.pausedSince = undefined;
    return thisPauseMs;
  }

  /** Push the next probe back (e.g. after a manual probe, to avoid doubling). */
  deferNextFatigue(): void {
    this.nextFatigueAtElapsed = this.elapsedMs + this.jitteredInterval();
  }

  end(reason: 'elapsed' | 'manual'): void {
    if (this.ended) return;
    this.ended = true;
    this.resume();
    this.clearTimers();
    this.hooks.onEnded(reason);
  }

  dispose(): void {
    this.ended = true;
    this.clearTimers();
  }

  private tick(): void {
    if (this.ended) return;
    if (this.pausedSince !== undefined) {
      this.hooks.onTick(this.remainingMs, this.elapsedMs);
      return;
    }
    const elapsed = this.elapsedMs;
    this.hooks.onTick(this.remainingMs, elapsed);

    if (elapsed >= this.cfg.durationMs) {
      this.end('elapsed');
      return;
    }

    const inQuietTail =
      this.cfg.durationMs - elapsed <= this.cfg.fatigueQuietTailMs;
    if (elapsed >= this.nextFatigueAtElapsed && !inQuietTail) {
      this.nextFatigueAtElapsed = elapsed + this.jitteredInterval();
      this.hooks.onFatigueDue();
    }
  }

  private jitteredInterval(): number {
    const r = Math.min(Math.max(this.cfg.fatigueJitterRatio, 0), 0.9);
    const factor = 1 + (Math.random() * 2 - 1) * r;
    return Math.max(30_000, this.cfg.fatigueIntervalMs * factor);
  }

  private clearTimers(): void {
    if (this.tickTimer) clearInterval(this.tickTimer);
    this.tickTimer = undefined;
  }
}
