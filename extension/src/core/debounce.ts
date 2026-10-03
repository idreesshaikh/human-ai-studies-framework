import { Disposable } from './types';

/**
 * Debouncers for high-frequency editor signals. Core so the emit semantics
 * (what the dataset actually contains) are unit-testable (NFR-3).
 */

/**
 * Leading + trailing debounce for `editor_focus` (250 ms per): the
 * FIRST value in a quiet period emits immediately; rapid follow-ups are
 * coalesced and the LAST one emits when the window goes quiet. Rapid
 * tab-cycling therefore emits first + last, never the tabs in between.
 */
export class FirstLastDebouncer<T> implements Disposable {
  private timer?: ReturnType<typeof setTimeout>;
  private pending?: { value: T };

  constructor(
    private readonly windowMs: number,
    private readonly emit: (value: T) => void,
  ) {}

  push(value: T): void {
    if (!this.timer) {
      this.emit(value);
      this.timer = setTimeout(() => this.expire(), this.windowMs);
      return;
    }
    this.pending = { value };
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.expire(), this.windowMs);
  }

  private expire(): void {
    this.timer = undefined;
    const p = this.pending;
    this.pending = undefined;
    if (p) this.emit(p.value);
  }

  dispose(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = undefined;
    this.pending = undefined;
  }
}

/**
 * Trailing-only debounce for `visible_range` (500 ms per editor): while the
 * participant scrolls, only the resting range emits.
 */
export class TrailingDebouncer<T> implements Disposable {
  private timer?: ReturnType<typeof setTimeout>;
  private pending?: { value: T };

  constructor(
    private readonly windowMs: number,
    private readonly emit: (value: T) => void,
  ) {}

  push(value: T): void {
    this.pending = { value };
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => this.expire(), this.windowMs);
  }

  private expire(): void {
    this.timer = undefined;
    const p = this.pending;
    this.pending = undefined;
    if (p) this.emit(p.value);
  }

  dispose(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = undefined;
    this.pending = undefined;
  }
}
