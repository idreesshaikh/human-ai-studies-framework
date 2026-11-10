import { Disposable } from './types';

/**
 * Tracks caret/hover dwell within a line region, excluding idle and blurred time.
 * This is a position proxy, not gaze: motionless reading and fast skimming can
 * be missed. Movement outside the region or a file switch closes the event.
 */

export type AttentionMode = 'reading' | 'editing' | 'mixed';
export type AttentionExit =
  'moved-away' | 'file-switch' | 'session-pause' | 'session-end';

/** A closed region, ready to be recorded as an `attention` event. */
export interface AttentionEvent {
  file: string;
  startLine: number;
  endLine: number;
  /** Present-and-active time on the region (`cursorMs + hoverMs`). */
  focusMs: number;
  /** Time attributed to the caret resting in the region. */
  cursorMs: number;
  /** Time attributed to the mouse hovering in the region. */
  hoverMs: number;
  /** True if any edit landed in the region while it was open. */
  edited: boolean;
  mode: AttentionMode;
  exitReason: AttentionExit;
}

export interface AttentionConfig {
  /** Caret/hover may wander +/- this many lines and stay the same region. */
  regionRadiusLines: number;
  /** Regions with less present time than this are dropped (pass-through). */
  minDwellMs: number;
}

/** Defaults; protocol-derivable via config (FR-PROT-4) like the other cores. */
export const DEFAULT_ATTENTION_CONFIG: AttentionConfig = {
  regionRadiusLines: 3,
  minDwellMs: 1_500,
};

type Source = 'cursor' | 'hover';

interface OpenRegion {
  file: string;
  anchorLine: number;
  cursorMs: number;
  hoverMs: number;
  edited: boolean;
  /** Start of the current, not-yet-banked time segment. */
  segmentStart: number;
  segmentSource: Source;
  /** True while present (window focused and not idle). */
  counting: boolean;
}

/**
 * Consumes cursor/hover/edit/presence signals and emits classified attention
 * regions. Fully event-driven - a region closes on caret/hover moving out of
 * the band, a file switch, or `flush()` (session pause / end).
 */
export class AttentionTracker implements Disposable {
  private open?: OpenRegion;
  private present = true;
  private readonly cfg: AttentionConfig;

  constructor(
    cfg: AttentionConfig,
    private readonly onAttention: (event: AttentionEvent) => void,
  ) {
    // Config is user-editable (settings.json can hold anything), so sanitize
    // here rather than trusting the adapter: a non-negative integer radius and
    // a non-negative dwell floor keep `sameRegion`/`close` from producing
    // NaN comparisons or startLine > endLine regardless of what is passed in.
    this.cfg = {
      regionRadiusLines: Math.max(0, Math.floor(cfg.regionRadiusLines)) || 0,
      minDwellMs: Math.max(0, cfg.minDwellMs) || 0,
    };
  }

  /** Caret or mouse-hover landed on `line` of `file` at time `at`. */
  look(source: Source, file: string, line: number, at: number): void {
    if (this.open && !this.sameRegion(file, line)) {
      this.close(at, this.open.file === file ? 'moved-away' : 'file-switch');
    }
    if (!this.open) {
      this.open = {
        file,
        anchorLine: line,
        cursorMs: 0,
        hoverMs: 0,
        edited: false,
        segmentStart: at,
        segmentSource: source,
        counting: this.present,
      };
      return;
    }
    // Same region: bank the running segment, then continue under `source`.
    this.bank(at);
    this.open.segmentSource = source;
  }

  /** An edit landed at `line` of `file`: implies caret presence, flags edited. */
  edit(file: string, line: number, at: number): void {
    this.look('cursor', file, line, at);
    if (this.open) this.open.edited = true;
  }

  /** Window blur / idle => pause the clock; focus / active => resume it. */
  setPresent(present: boolean, at: number): void {
    if (present === this.present) return;
    if (!present && this.open) this.bank(at); // bank before pausing
    this.present = present;
    if (this.open) {
      this.open.counting = present;
      if (present) this.open.segmentStart = at; // away-time is not counted
    }
  }

  /** Close any open region (session pause / end). */
  flush(at: number, reason: AttentionExit = 'session-end'): void {
    this.close(at, reason);
  }

  dispose(): void {
    this.flush(Date.now(), 'session-end');
  }

  private sameRegion(file: string, line: number): boolean {
    return (
      !!this.open &&
      this.open.file === file &&
      Math.abs(line - this.open.anchorLine) <= this.cfg.regionRadiusLines
    );
  }

  /** Add the elapsed segment to its source's clock and restart the segment. */
  private bank(at: number): void {
    const o = this.open;
    if (!o) return;
    if (o.counting) {
      const delta = at - o.segmentStart;
      if (delta > 0) {
        if (o.segmentSource === 'cursor') o.cursorMs += delta;
        else o.hoverMs += delta;
      }
    }
    o.segmentStart = at;
  }

  private close(at: number, reason: AttentionExit): void {
    const o = this.open;
    if (!o) return;
    this.bank(at);
    this.open = undefined;
    const focusMs = o.cursorMs + o.hoverMs;
    if (focusMs < this.cfg.minDwellMs) return; // pass-through glance, not dwell
    const r = this.cfg.regionRadiusLines;
    this.onAttention({
      file: o.file,
      startLine: Math.max(0, o.anchorLine - r),
      endLine: o.anchorLine + r,
      focusMs,
      cursorMs: o.cursorMs,
      hoverMs: o.hoverMs,
      edited: o.edited,
      mode: this.classify(o),
      exitReason: reason,
    });
  }

  private classify(o: OpenRegion): AttentionMode {
    if (o.edited) return 'editing';
    if (o.cursorMs > 0 && o.hoverMs > 0) return 'mixed';
    return 'reading';
  }
}
