import { Disposable } from './types';

/**
 * Aggregates content-free edit signals and classifies burst origin.
 * Precedence: undo/redo, correlated AI acceptance, correlated paste, bulk-edit
 * heuristic, then human typing. Unobserved paste, streaming AI edits, external
 * file changes, and delayed acceptance signals can be misclassified.
 */

/** Origin classification of an edit burst (FR-INST-10). */
export type EditOrigin = 'human' | 'ai' | 'paste' | 'undo-redo';

/**
 * One primitive document-change signal from the adapter. Sizes and shapes
 * only - the adapter must never forward text content.
 */
export interface ChangeSignal {
  /** Stable file identifier (workspace-relative path). */
  fileKey: string;
  charsAdded: number;
  charsDeleted: number;
  /** Lines touched by this change. */
  lines: number;
  /** Millisecond timestamp (adapters pass their monotonic-ish clock). */
  tsMono: number;
  /** True when the IDE flagged this change as an undo or redo. */
  undoRedo?: boolean;
}

/** A closed burst, ready to be recorded as an `edit_burst` event. */
export interface EditBurst {
  file: string;
  charsAdded: number;
  charsDeleted: number;
  linesTouched: number;
  durationMs: number;
  origin: EditOrigin;
}

export interface BurstConfig {
  /** A burst closes after this long without further changes. */
  gapMs: number;
  /** How often the close-check timer runs. */
  checkIntervalMs: number;
  /** Accepted-AI-suggestion correlation window around the burst. */
  aiCorrelationMs: number;
  /** Chars that must land within `aiBlockMaxDurationMs` to look injected. */
  aiBlockCharThreshold: number;
  /** Window for the block-injection heuristic. */
  aiBlockMaxDurationMs: number;
  /** Clipboard-paste correlation window around the burst. */
  pasteCorrelationMs: number;
}

/** Defaults per; all protocol-derivable via config (FR-PROT-4). */
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
  /** Recent additions inside the block-heuristic window. */
  recentAdds: { at: number; chars: number }[];
}

/**
 * Consumes primitive change signals and emits classified edit bursts.
 * A burst closes after `gapMs` without changes, on a file switch, or on
 * `flush()` (session end / pause). Timer-driven like `StuckDetector`, so it
 * is unit-testable with mocked timers.
 */
export class BurstAggregator implements Disposable {
  private timer?: ReturnType<typeof setInterval>;
  private open?: OpenBurst;
  private lastAiAccept?: { at: number; file?: string };
  private lastPaste?: { at: number; file?: string };

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

  /** The adapter saw an AI suggestion get accepted (FR-INST-8 hook). */
  noteAiAccept(tsMono: number, file?: string): void {
    this.lastAiAccept = { at: tsMono, file };
  }

  /** The adapter saw a clipboard paste (wrapped paste command). */
  notePaste(tsMono: number, file?: string): void {
    this.lastPaste = { at: tsMono, file };
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

    // Block-injection heuristic: enough chars inside a tiny window.
    if (s.charsAdded > 0) {
      b.recentAdds.push({ at: s.tsMono, chars: s.charsAdded });
      const cutoff = s.tsMono - this.cfg.aiBlockMaxDurationMs;
      b.recentAdds = b.recentAdds.filter((r) => r.at >= cutoff);
      const windowChars = b.recentAdds.reduce((sum, r) => sum + r.chars, 0);
      if (windowChars >= this.cfg.aiBlockCharThreshold) b.hadAiBlock = true;
    }
  }

  /** Close any open burst immediately (file switch, pause, session end). */
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

  /** Priority order per FR-INST-10 - see the module doc for the rationale. */
  private classify(b: OpenBurst): EditOrigin {
    if (b.hadUndoRedo) return 'undo-redo';
    if (this.correlates(this.lastAiAccept, b, this.cfg.aiCorrelationMs)) {
      return 'ai';
    }
    if (this.correlates(this.lastPaste, b, this.cfg.pasteCorrelationMs)) {
      return 'paste';
    }
    if (b.hadAiBlock) return 'ai';
    return 'human';
  }

  /** Did `at` land within `windowMs` of the burst's span? */
  private correlates(
    signal: { at: number; file?: string } | undefined,
    b: OpenBurst,
    windowMs: number,
  ): boolean {
    return (
      signal !== undefined &&
      (signal.file === undefined || signal.file === b.file) &&
      signal.at >= b.firstAt - windowMs &&
      signal.at <= b.lastAt + windowMs
    );
  }
}
