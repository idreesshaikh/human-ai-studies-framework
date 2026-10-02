import { Disposable } from './types';

export type AttentionMode = 'reading' | 'editing' | 'mixed';
export type AttentionExit =
  'moved-away' | 'file-switch' | 'session-pause' | 'session-end';

export interface AttentionEvent {
  file: string;
  startLine: number;
  endLine: number;

  focusMs: number;

  cursorMs: number;

  hoverMs: number;

  edited: boolean;
  mode: AttentionMode;
  exitReason: AttentionExit;
}

export interface AttentionConfig {
  regionRadiusLines: number;

  minDwellMs: number;
}

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

  segmentStart: number;
  segmentSource: Source;

  counting: boolean;
}

export class AttentionTracker implements Disposable {
  private open?: OpenRegion;
  private present = true;
  private readonly cfg: AttentionConfig;

  constructor(
    cfg: AttentionConfig,
    private readonly onAttention: (event: AttentionEvent) => void,
  ) {
    this.cfg = {
      regionRadiusLines: Math.max(0, Math.floor(cfg.regionRadiusLines)) || 0,
      minDwellMs: Math.max(0, cfg.minDwellMs) || 0,
    };
  }

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

    this.bank(at);
    this.open.segmentSource = source;
  }

  edit(file: string, line: number, at: number): void {
    this.look('cursor', file, line, at);
    if (this.open) this.open.edited = true;
  }

  setPresent(present: boolean, at: number): void {
    if (present === this.present) return;
    if (!present && this.open) this.bank(at);
    this.present = present;
    if (this.open) {
      this.open.counting = present;
      if (present) this.open.segmentStart = at;
    }
  }

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
    if (focusMs < this.cfg.minDwellMs) return;
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
