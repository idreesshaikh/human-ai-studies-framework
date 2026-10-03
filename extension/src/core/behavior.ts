import { Disposable } from './types';

export type EditOrigin = 'human' | 'ai' | 'paste' | 'undo-redo';

export interface ChangeSignal {
  fileKey: string;
  charsAdded: number;
  charsDeleted: number;

  lines: number;

  tsMono: number;

  undoRedo?: boolean;
}

export interface EditBurst {
  file: string;
  charsAdded: number;
  charsDeleted: number;
  linesTouched: number;
  durationMs: number;
  origin: EditOrigin;
}

export interface BurstConfig {
  gapMs: number;

  checkIntervalMs: number;

  aiCorrelationMs: number;

  aiBlockCharThreshold: number;

  aiBlockMaxDurationMs: number;

  pasteCorrelationMs: number;
}

export const DEFAULT_BURST_CONFIG: BurstConfig = {
  gapMs: 2_000,
  checkIntervalMs: 500,
  aiCorrelationMs: 500,
  aiBlockCharThreshold: 80,
  aiBlockMaxDurationMs: 50,
  pasteCorrelationMs: 100,
};

interface OpenBurst {
  file: string;
  firstAt: number;
  lastAt: number;
  charsAdded: number;
  charsDeleted: number;
  linesTouched: number;
  hadUndoRedo: boolean;
  hadAiBlock: boolean;

  recentAdds: { at: number; chars: number }[];
}

export class BurstAggregator implements Disposable {
  private timer?: ReturnType<typeof setInterval>;
  private open?: OpenBurst;
  private lastAiAcceptAt = Number.NEGATIVE_INFINITY;
  private lastPasteAt = Number.NEGATIVE_INFINITY;

  constructor(
    private readonly cfg: BurstConfig,
    private readonly onBurst: (burst: EditBurst) => void,
  ) {}

  start(): void {
    this.stop();
    this.timer = setInterval(() => this.check(), this.cfg.checkIntervalMs);
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = undefined;
    }
  }

  dispose(): void {
    this.flush();
    this.stop();
  }

  noteAiAccept(tsMono: number): void {
    this.lastAiAcceptAt = tsMono;
  }

  notePaste(tsMono: number): void {
    this.lastPasteAt = tsMono;
  }

  change(s: ChangeSignal): void {
    if (this.open && this.open.file !== s.fileKey) {
      this.close();
    }
    if (!this.open) {
      this.open = {
        file: s.fileKey,
        firstAt: s.tsMono,
        lastAt: s.tsMono,
        charsAdded: 0,
        charsDeleted: 0,
        linesTouched: 0,
        hadUndoRedo: false,
        hadAiBlock: false,
        recentAdds: [],
      };
    }
    const b = this.open;
    b.lastAt = s.tsMono;
    b.charsAdded += s.charsAdded;
    b.charsDeleted += s.charsDeleted;
    b.linesTouched += s.lines;
    if (s.undoRedo) b.hadUndoRedo = true;

    if (s.charsAdded > 0) {
      b.recentAdds.push({ at: s.tsMono, chars: s.charsAdded });
      const cutoff = s.tsMono - this.cfg.aiBlockMaxDurationMs;
      b.recentAdds = b.recentAdds.filter((r) => r.at >= cutoff);
      const windowChars = b.recentAdds.reduce((sum, r) => sum + r.chars, 0);
      if (windowChars >= this.cfg.aiBlockCharThreshold) b.hadAiBlock = true;
    }
  }

  flush(): void {
    this.close();
  }

  private check(): void {
    if (!this.open) return;
    if (Date.now() - this.open.lastAt >= this.cfg.gapMs) this.close();
  }

  private close(): void {
    const b = this.open;
    if (!b) return;
    this.open = undefined;
    this.onBurst({
      file: b.file,
      charsAdded: b.charsAdded,
      charsDeleted: b.charsDeleted,
      linesTouched: b.linesTouched,
      durationMs: b.lastAt - b.firstAt,
      origin: this.classify(b),
    });
  }

  private classify(b: OpenBurst): EditOrigin {
    if (b.hadUndoRedo) return 'undo-redo';
    if (this.correlates(this.lastAiAcceptAt, b, this.cfg.aiCorrelationMs)) {
      return 'ai';
    }
    if (this.correlates(this.lastPasteAt, b, this.cfg.pasteCorrelationMs)) {
      return 'paste';
    }
    if (b.hadAiBlock) return 'ai';
    return 'human';
  }

  private correlates(at: number, b: OpenBurst, windowMs: number): boolean {
    return at >= b.firstAt - windowMs && at <= b.lastAt + windowMs;
  }
}
