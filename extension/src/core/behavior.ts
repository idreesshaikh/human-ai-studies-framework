import { Disposable } from './types';

/**
 * Edit-burst aggregation and origin classification for the behavioral
 * telemetry leg (FR-INST-5, FR-INST-10). Pure logic, no IDE imports (NFR-3).
 *
 * The adapter feeds primitive change signals (sizes and shapes only - never
 * text content, FR-ETH-2); this module aggregates them into bursts and
 * classifies each burst's origin.
 *
 * ## Origin heuristic (FR-INST-10)
 *
 * Evidence is ranked per burst, strongest first:
 *
 *  1. `undo-redo` - the IDE itself flags undo/redo document changes; this is
 *     ground truth, never a guess.
 *  2. `ai` (correlated) - an accepted AI suggestion was signalled within
 *     `aiCorrelationMs` of the burst. Direct evidence from the completion
 *     lifecycle hooks.
 *  3. `paste` - a clipboard-paste signal landed within `pasteCorrelationMs`
 *     of the burst. Direct evidence from the wrapped paste command.
 *  4. `ai` (block heuristic) - at least `aiBlockCharThreshold` chars arrived
 *     within `aiBlockMaxDurationMs` (the behavior doc's "massive block in
 *     1 ms" - humans do not type 80 chars in 50 ms). Circumstantial, so it
 *     ranks BELOW paste correlation: a large paste satisfies both, and the
 *     paste signal is direct evidence while block size is not.
 *  5. `human` - otherwise: incremental typing.
 *
 * ## Known failure modes (documented per FR-INST-10)
 *
 *  - AI tools that stream insertions keystroke-by-keystroke (rare) evade the
 *    block heuristic; they are only caught via accept-correlation (2).
 *  - Pastes that bypass the wrapped paste command (context-menu paste, drag
 *    & drop) emit no paste signal; large ones misclassify as `ai` via (4),
 *    small ones as `human`.
 *  - External tools editing files on disk (e.g. a CLI agent) surface as
 *    bulk document changes when the editor reloads; they classify as `ai`
 *    via (4), which for agent-driven studies is usually the right call.
 *  - Correlation windows are wall-clock; a suggestion accepted > 500 ms
 *    before its text lands (slow extension host) misses the window.
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

  /** The adapter saw an AI suggestion get accepted (FR-INST-8 hook). */
  noteAiAccept(tsMono: number): void {
    this.lastAiAcceptAt = tsMono;
  }

  /** The adapter saw a clipboard paste (wrapped paste command). */
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
    if (this.correlates(this.lastAiAcceptAt, b, this.cfg.aiCorrelationMs)) {
      return 'ai';
    }
    if (this.correlates(this.lastPasteAt, b, this.cfg.pasteCorrelationMs)) {
      return 'paste';
    }
    if (b.hadAiBlock) return 'ai';
    return 'human';
  }

  /** Did `at` land within `windowMs` of the burst's span? */
  private correlates(at: number, b: OpenBurst, windowMs: number): boolean {
    return at >= b.firstAt - windowMs && at <= b.lastAt + windowMs;
  }
}
