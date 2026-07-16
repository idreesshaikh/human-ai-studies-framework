import { Disposable } from './types';

export type ActivityState = 'active' | 'idle';

export interface IdleConfig {
  /** No interaction for this long => idle (FR-INST-11; default 120 s). */
  windowMs: number;
  /** How often the state check runs. */
  checkIntervalMs: number;
}

export const DEFAULT_IDLE_CONFIG: IdleConfig = {
  windowMs: 120_000,
  checkIntervalMs: 5_000,
};

/**
 * WakaTime-style active/idle state machine (FR-INST-11, decision D4):
 * "active" means any interaction within a rolling window. Emits TRANSITIONS
 * only - never periodic heartbeat spam - so time-on-task analysis can
 * subtract editor-open-but-absent periods with two rows per gap.
 *
 * Pure logic, no IDE imports (NFR-3); timer-driven like `StuckDetector` so
 * mocked-timer tests apply.
 */
export class IdleDetector implements Disposable {
  private timer?: ReturnType<typeof setInterval>;
  private lastActivityAt = 0;
  private state: ActivityState = 'active';

  constructor(
    private readonly cfg: IdleConfig,
    private readonly onTransition: (state: ActivityState) => void,
  ) {}

  /** Starts in `active` without emitting - only transitions are events. */
  start(): void {
    this.stop();
    this.lastActivityAt = Date.now();
    this.state = 'active';
    this.timer = setInterval(() => this.check(), this.cfg.checkIntervalMs);
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = undefined;
    }
  }

  dispose(): void {
    this.stop();
  }

  /** Any participant interaction (edit, scroll, focus, selection...). */
  activity(at: number): void {
    this.lastActivityAt = at;
    if (this.state === 'idle') {
      this.state = 'active';
      this.onTransition('active');
    }
  }

  private check(): void {
    if (this.state !== 'active') return;
    if (Date.now() - this.lastActivityAt >= this.cfg.windowMs) {
      this.state = 'idle';
      this.onTransition('idle');
    }
  }
}
