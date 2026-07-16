import { Disposable, EditorSignal, StuckRegion } from './types';

export interface StuckDetectorConfig {
  /** Dwelling this long on one region without editing => stuck. */
  stuckAfterMs: number;
  /** Cursor may wander +/- this many lines and still count as the same region. */
  dwellLineRadius: number;
  /**
   * If NO signals at all arrive for this long, the participant is treated as
   * idle/away rather than stuck. Without eye tracking, perfectly motionless
   * staring is indistinguishable from being away from the keyboard, so we
   * require faint activity (cursor moves, scrolling, focus) to call it stuck.
   */
  idleAfterMs: number;
  /** Minimum gap between two stuck prompts. */
  cooldownMs: number;
  /** Window for the scroll-oscillation heuristic. */
  scrollWindowMs: number;
  /** Direction flips within the window that indicate re-reading back & forth. */
  scrollDirectionFlips: number;
  /** How often the internal heuristic check runs. */
  checkIntervalMs: number;
}

export const DEFAULT_STUCK_CONFIG: StuckDetectorConfig = {
  stuckAfterMs: 90_000,
  dwellLineRadius: 6,
  idleAfterMs: 45_000,
  cooldownMs: 5 * 60_000,
  scrollWindowMs: 60_000,
  scrollDirectionFlips: 4,
  checkIntervalMs: 5_000,
};

interface ScrollSample {
  at: number;
  mid: number;
  file: string;
}

/**
 * Heuristic stuck detection from normalized editor signals.
 *
 * Two independent patterns fire the callback:
 *  1. DWELL - the cursor stays within a small line radius, the participant is
 *     demonstrably active (signals keep arriving), yet no edits happen for
 *     `stuckAfterMs`. Classic "staring at the same function" pattern.
 *  2. SCROLL-THRASH - the visible range oscillates up/down over the same area
 *     several times within a minute: re-reading without progress.
 *
 * Pure logic, no IDE imports - unit-testable and portable.
 */
export class StuckDetector implements Disposable {
  private timer?: ReturnType<typeof setInterval>;
  private lastSignalAt = 0;
  private lastEditAt = 0;
  private lastPromptAt = 0;
  private focused = true;
  private anchor?: { file: string; line: number; since: number };
  private scrollSamples: ScrollSample[] = [];

  constructor(
    private readonly cfg: StuckDetectorConfig,
    private readonly onStuck: (region: StuckRegion) => void,
  ) {}

  start(): void {
    this.stop();
    const now = Date.now();
    this.lastSignalAt = now;
    this.lastEditAt = now;
    this.lastPromptAt = 0;
    this.timer = setInterval(() => this.check(), this.cfg.checkIntervalMs);
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = undefined;
    }
    this.anchor = undefined;
    this.scrollSamples = [];
  }

  dispose(): void {
    this.stop();
  }

  /** Called by the adapter whenever a prompt (any prompt) is shown, so the
   *  detector does not immediately re-fire while one is on screen. */
  notePromptShown(): void {
    this.lastPromptAt = Date.now();
  }

  /** Epoch ms of the last text edit - adapters use this to time prompts
   *  into natural pauses instead of interrupting typing. */
  get lastEditTime(): number {
    return this.lastEditAt;
  }

  signal(s: EditorSignal): void {
    this.lastSignalAt = s.at;

    switch (s.kind) {
      case 'edit':
        this.lastEditAt = s.at;
        // Editing is progress: restart the dwell clock where they are.
        if (this.anchor && s.file === this.anchor.file) {
          this.anchor.since = s.at;
        }
        break;

      case 'selection':
        if (s.file === undefined || s.line === undefined) break;
        if (
          this.anchor &&
          this.anchor.file === s.file &&
          Math.abs(s.line - this.anchor.line) <= this.cfg.dwellLineRadius
        ) {
          // Still hovering around the same region - keep the anchor aging.
        } else {
          this.anchor = { file: s.file, line: s.line, since: s.at };
        }
        break;

      case 'scroll': {
        if (s.file === undefined || s.line === undefined) break;
        if (
          this.scrollSamples.length &&
          this.scrollSamples[this.scrollSamples.length - 1].file !== s.file
        ) {
          this.scrollSamples = [];
        }
        this.scrollSamples.push({ at: s.at, mid: s.line, file: s.file });
        // Keep only the analysis window.
        const cutoff = s.at - this.cfg.scrollWindowMs;
        this.scrollSamples = this.scrollSamples.filter((x) => x.at >= cutoff);
        break;
      }

      case 'focus':
        this.focused = true;
        break;
      case 'blur':
        this.focused = false;
        break;
    }
  }

  private check(): void {
    const now = Date.now();
    if (!this.focused) return;
    if (now - this.lastPromptAt < this.cfg.cooldownMs) return;
    // Idle gate: no faint activity => away, not stuck.
    if (now - this.lastSignalAt > this.cfg.idleAfterMs) return;

    const dwell = this.checkDwell(now);
    if (dwell) {
      this.fire(dwell, now);
      return;
    }
    const thrash = this.checkScrollThrash(now);
    if (thrash) {
      this.fire(thrash, now);
    }
  }

  private checkDwell(now: number): StuckRegion | undefined {
    if (!this.anchor) return undefined;
    const clockStart = Math.max(
      this.anchor.since,
      this.lastEditAt,
      this.lastPromptAt,
    );
    const elapsed = now - clockStart;
    if (elapsed < this.cfg.stuckAfterMs) return undefined;
    const r = this.cfg.dwellLineRadius;
    return {
      file: this.anchor.file,
      startLine: Math.max(0, this.anchor.line - r),
      endLine: this.anchor.line + r,
      reason: 'dwell',
      evidenceMs: elapsed,
    };
  }

  private checkScrollThrash(now: number): StuckRegion | undefined {
    const samples = this.scrollSamples.filter(
      (s) => s.at >= now - this.cfg.scrollWindowMs,
    );
    if (samples.length < this.cfg.scrollDirectionFlips + 2) return undefined;
    // Editing recently means they are making progress, not thrashing.
    if (now - this.lastEditAt < this.cfg.stuckAfterMs / 2) return undefined;

    let flips = 0;
    let prevDir = 0;
    for (let i = 1; i < samples.length; i++) {
      const delta = samples[i].mid - samples[i - 1].mid;
      if (delta === 0) continue;
      const dir = Math.sign(delta);
      if (prevDir !== 0 && dir !== prevDir) flips++;
      prevDir = dir;
    }
    if (flips < this.cfg.scrollDirectionFlips) return undefined;

    const mids = samples.map((s) => s.mid);
    const span = Math.max(...mids) - Math.min(...mids);
    // Oscillating across a huge distance is navigation, not re-reading.
    if (span > 200) return undefined;

    return {
      file: samples[samples.length - 1].file,
      startLine: Math.max(0, Math.min(...mids)),
      endLine: Math.max(...mids),
      reason: 'scroll-thrash',
      evidenceMs: samples[samples.length - 1].at - samples[0].at,
    };
  }

  private fire(region: StuckRegion, now: number): void {
    this.lastPromptAt = now;
    this.scrollSamples = [];
    if (this.anchor) this.anchor.since = now;
    this.onStuck(region);
  }
}
