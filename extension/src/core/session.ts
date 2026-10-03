import { Disposable, StudyCondition } from './types';

export interface SessionConfig {
  participantId: string;
  condition: StudyCondition;
  durationMs: number;

  fatigueIntervalMs: number;

  fatigueJitterRatio: number;

  fatigueQuietTailMs: number;
}

export interface SessionHooks {
  onFatigueDue(): void;

  onEnded(reason: 'elapsed' | 'manual'): void;

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

    plannedId?: string,
  ) {
    this.id = restore?.sessionId ?? plannedId ?? newSessionId();
    this.startedAt = restore?.startedAtEpochMs ?? Date.now();
    this.pausedMsTotal = restore?.pausedMsAccumulated ?? 0;
    this.nextFatigueAtElapsed = this.elapsedMs + this.jitteredInterval();
    this.tickTimer = setInterval(() => this.tick(), 1_000);
  }

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

  resume(): number {
    if (this.pausedSince === undefined) return 0;
    const thisPauseMs = Date.now() - this.pausedSince;
    this.pausedMsTotal += thisPauseMs;
    this.pausedSince = undefined;
    return thisPauseMs;
  }

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
