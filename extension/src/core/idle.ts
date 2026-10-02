import { Disposable } from './types';

export type ActivityState = 'active' | 'idle';

export interface IdleConfig {
  windowMs: number;

  checkIntervalMs: number;
}

export const DEFAULT_IDLE_CONFIG: IdleConfig = {
  windowMs: 120_000,
  checkIntervalMs: 5_000,
};

export class IdleDetector implements Disposable {
  private timer?: ReturnType<typeof setInterval>;
  private lastActivityAt = 0;
  private state: ActivityState = 'active';

  constructor(
    private readonly cfg: IdleConfig,
    private readonly onTransition: (state: ActivityState) => void,
  ) {}

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
