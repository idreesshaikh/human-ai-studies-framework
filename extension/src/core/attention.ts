import { Disposable } from './types';

/**
 * Region-level attention / time-on-code tracking (fills the behavior doc's
 * "time spent on a specific line of code" data point, which MP-05 left
 * unmeasured: `heartbeat` gives whole-session active time and `editor_focus`
 * lets analysis reconstruct per-file time, but nothing measured per-region
 * dwell). Pure logic, no IDE imports (NFR-3); driven entirely by timestamped
 * signals so it is deterministic under mocked timers like the other cores.
 *
 * ## What it measures
 *
 * "Where is the participant's attention" has no ground truth without eye
 * tracking, so we approximate it from two signals the adapter forwards:
 *
 *  - `cursor` - the caret line (where they are positioned / editing).
 *  - `hover`  - a mouse-hover ping (where they are *reading* without moving
 *    the caret - people point at code they read). Discrete pings, accumulated.
 *
 * A region is a line +/- `regionRadiusLines` band (like StuckDetector's dwell
 * radius): movement within the band stays the same region so caret jitter and
 * reading a line up/down does not shatter the metric. Leaving the band, or
 * switching files, closes the region and emits one `attention` event.
 *
 * ## Honest gating (why the number is trustworthy)
 *
 * Time only accrues while the participant is *present* - the adapter calls
 * `setPresent(false)` on window blur or idle and `setPresent(true)` on return,
 * so a coffee break is banked as zero, not as an hour on line 12. The clock is
 * partitioned into `cursorMs` vs `hoverMs` by which signal was most recent, and
 * `focusMs = cursorMs + hoverMs` is the present-and-active total.
 *
 * ## Known failure modes
 *
 *  - It is caret/pointer position, not gaze: a participant can read line 10
 *    while the caret sits on line 50 and never hovers - undercounted.
 *  - Perfectly motionless reading (no caret move, no hover) eventually trips
 *    the idle gate and stops the clock - the deliberate trade-off of not
 *    counting away-time as attention.
 *  - Hover pings only fire after the mouse rests briefly on hoverable content;
 *    fast skimming and hovering over blank lines register nothing.
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
