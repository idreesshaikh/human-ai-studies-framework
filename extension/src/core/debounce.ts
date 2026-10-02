import { Disposable } from './types';

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
