import { Disposable } from './types';

export interface IdeHealthConfig {
  debounceMs: number;
}

export const DEFAULT_IDE_HEALTH_CONFIG: IdeHealthConfig = {
  debounceMs: 10_000,
};

export interface IdeHealthSnapshot {
  errorCount: number;
  warningCount: number;
  buildInvocations: number;
  testInvocations: number;
}

export interface IdeHealthEvent {
  type: 'ide_health';
  ts: number;
  mono: number;
  seq: number;
  errorCount: number;
  warningCount: number;
  buildInvocations: number;
  testInvocations: number;
}

export type DiagnosticKind = 'error' | 'warning';
export type InvocationKind = 'build' | 'test';

export type HealthEventSink = (event: IdeHealthEvent) => void;

export class IdeHealthCollector implements Disposable {
  private _errorCount = 0;
  private _warningCount = 0;
  private _buildInvocations = 0;
  private _testInvocations = 0;
  private _seq = 0;
  private _debounceTimer?: ReturnType<typeof setTimeout>;
  private _onFlush: HealthEventSink;

  constructor(
    private _config: IdeHealthConfig,
    onFlush: HealthEventSink,
    private _clock: () => number = () => Date.now(),
  ) {
    this._onFlush = onFlush;
  }

  recordDiagnostics(errors: number, warnings: number): void {
    this._errorCount += errors;
    this._warningCount += warnings;
    this._scheduleFlush();
  }

  recordInvocation(kind: InvocationKind): void {
    if (kind === 'build') this._buildInvocations += 1;
    else this._testInvocations += 1;
    this._scheduleFlush();
  }

  reset(): void {
    this._errorCount = 0;
    this._warningCount = 0;
    this._buildInvocations = 0;
    this._testInvocations = 0;
    this._seq = 0;
    this._debounceTimer = undefined;
  }

  snapshot(): IdeHealthSnapshot {
    return {
      errorCount: this._errorCount,
      warningCount: this._warningCount,
      buildInvocations: this._buildInvocations,
      testInvocations: this._testInvocations,
    };
  }

  flush(): void {
    if (this._debounceTimer) {
      clearTimeout(this._debounceTimer);
      this._debounceTimer = undefined;
    }
    const now = this._clock();
    if (
      this._errorCount === 0 &&
      this._warningCount === 0 &&
      this._buildInvocations === 0 &&
      this._testInvocations === 0
    ) {
      return;
    }
    this._seq += 1;
    const event: IdeHealthEvent = {
      type: 'ide_health',
      ts: now / 1000,
      mono: performance.now(),
      seq: this._seq,
      errorCount: this._errorCount,
      warningCount: this._warningCount,
      buildInvocations: this._buildInvocations,
      testInvocations: this._testInvocations,
    };
    this._errorCount = 0;
    this._warningCount = 0;
    this._buildInvocations = 0;
    this._testInvocations = 0;
    this._onFlush(event);
  }

  private _scheduleFlush(): void {
    if (this._debounceTimer) clearTimeout(this._debounceTimer);
    this._debounceTimer = setTimeout(
      () => this.flush(),
      this._config.debounceMs,
    );
  }

  dispose(): void {
    this.flush();
    if (this._debounceTimer) clearTimeout(this._debounceTimer);
    this._onFlush = () => {};
  }
}
