import { EditOrigin } from '../../src/core/behavior';

/**
 * Scripted scenarios. They characterise rule behaviour and known failure
 * modes against the signals as modelled here; they are NOT an accuracy
 * estimate for real developer sessions. `expected` is the label a human
 * observer would give (or, for boundary cases, the rule's documented intent).
 * Separate bursts by more than the 2 s gap (we use >= 3 s).
 */

export type EditEvent =
  | {
      t: number;
      kind: 'change';
      fileKey?: string;
      charsAdded: number;
      charsDeleted?: number;
      lines?: number;
      undoRedo?: boolean;
    }
  | { t: number; kind: 'aiAccept' }
  | { t: number; kind: 'paste' };

export interface EditScenario {
  id: string;
  description: string;
  /** Ground-truth origin per burst, in order. */
  expected: EditOrigin[];
  /** Offsets in ms from scenario start, non-decreasing. */
  events: EditEvent[];
  /** Set when the rule is expected to get this wrong; says why. */
  knownFailure?: string;
}

export interface StuckEvent {
  t: number;
  kind: 'edit' | 'selection' | 'scroll' | 'focus' | 'blur' | 'prompt';
  file?: string;
  line?: number;
}

export interface StuckScenario {
  id: string;
  description: string;
  /** Ground truth: is the person genuinely stuck from `stuckFromMs`? */
  stuck: boolean;
  stuckFromMs: number;
  durationMs: number;
  events: StuckEvent[];
  /** Exact number of prompts the detector is expected to fire. */
  expectedFires: number;
  /** Required when a non-stuck scenario fires. */
  knownFalseAlarm?: string;
}

// ---------------------------------------------------------------- edit

const chg = (t: number, charsAdded: number, more = {}): EditEvent => ({
  t,
  kind: 'change',
  charsAdded,
  ...more,
});
const typed = (from: number, n: number, step = 250): EditEvent[] =>
  Array.from({ length: n }, (_, i) => chg(from + i * step, 1));

const AI_LAG = 'accept signal outside the 500 ms window (slow extension host)';
const PASTE_LAG = 'paste signal outside the 100 ms window';

/** A single 30-char burst at t=1000 with one signal at `signalT`. */
function lagged(
  id: string,
  kind: 'aiAccept' | 'paste',
  expected: EditOrigin,
  signalT: number,
  failure?: string,
): EditScenario {
  const events: EditEvent[] = [chg(1_000, 30), { t: signalT, kind }];
  events.sort((a, b) => a.t - b.t);
  return {
    id,
    description: `${kind} signal at t=${signalT} vs 30-char burst at t=1000`,
    expected: [expected],
    events,
    knownFailure: failure,
  };
}

export const EDIT_SCENARIOS: EditScenario[] = [
  {
    id: 'typing-plain',
    description: '12 single-char keystrokes, 250 ms apart',
    expected: ['human'],
    events: typed(0, 12),
  },
  {
    id: 'paste-signal-large',
    description:
      'keybinding paste of 200 chars, signal stamped at first change',
    expected: ['paste'],
    events: [{ t: 0, kind: 'paste' }, chg(0, 200, { lines: 8 })],
  },
  {
    id: 'paste-signal-small',
    description: 'keybinding paste of 15 chars with signal',
    expected: ['paste'],
    events: [{ t: 0, kind: 'paste' }, chg(0, 15)],
  },
  {
    id: 'ai-accept-block',
    description: 'accepted inline suggestion, 120 chars, with accept signal',
    expected: ['ai'],
    events: [{ t: 0, kind: 'aiAccept' }, chg(0, 120, { lines: 4 })],
  },
  {
    id: 'ai-accept-small',
    description: 'accepted 30-char suggestion (below block size), with signal',
    expected: ['ai'],
    events: [{ t: 0, kind: 'aiAccept' }, chg(0, 30)],
  },
  {
    id: 'undo',
    description: 'undo flagged by the IDE',
    expected: ['undo-redo'],
    events: [chg(0, 0, { charsDeleted: 12, undoRedo: true })],
  },
  {
    id: 'undo-large-with-paste-signal',
    description: 'redo restoring 200 chars while a stale paste signal exists',
    expected: ['undo-redo'],
    events: [{ t: 0, kind: 'paste' }, chg(0, 200, { undoRedo: true })],
  },
  {
    id: 'ai-and-paste-signals',
    description: 'both accept and paste signals present: accept outranks',
    expected: ['ai'],
    events: [{ t: 0, kind: 'aiAccept' }, { t: 0, kind: 'paste' }, chg(0, 90)],
  },
  {
    id: 'sequence-mixed',
    description: 'typing, paste, accept, undo, typing; each burst 3 s apart',
    expected: ['human', 'paste', 'ai', 'undo-redo', 'human'],
    events: [
      ...typed(0, 4),
      { t: 5_000, kind: 'paste' },
      chg(5_000, 40),
      { t: 10_000, kind: 'aiAccept' },
      chg(10_000, 60),
      chg(15_000, 0, { charsDeleted: 60, undoRedo: true }),
      ...typed(20_000, 4),
    ],
  },
  {
    id: 'context-menu-paste-large',
    description: '300-char paste via context menu / drag-drop, no paste signal',
    expected: ['paste'],
    events: [chg(0, 300, { lines: 12 })],
    knownFailure:
      'behavior.ts known failure: unwrapped paste >= 80 chars lands as ai via the block heuristic',
  },
  {
    id: 'context-menu-paste-small',
    description: '30-char context-menu paste, no paste signal',
    expected: ['paste'],
    events: [chg(0, 30)],
    knownFailure:
      'behavior.ts known failure: unwrapped small paste lands as human',
  },
  {
    id: 'external-agent-bulk',
    description: 'CLI agent rewrites file on disk; 500 chars arrive at once',
    expected: ['ai'],
    events: [chg(0, 500, { lines: 20 })],
  },
  {
    id: 'ai-streaming-no-signal',
    description: 'AI streams 5 chars every 20 ms for 1 s, no accept signal',
    expected: ['ai'],
    events: Array.from({ length: 50 }, (_, i) => chg(i * 20, 5)),
    knownFailure:
      'behavior.ts known failure: keystroke-paced streaming evades the block heuristic',
  },
  {
    id: 'boundary-79-chars',
    description: 'single 79-char insertion, no signals',
    expected: ['human'],
    events: [chg(0, 79)],
  },
  {
    id: 'boundary-80-chars',
    description: 'single 80-char insertion, no signals',
    expected: ['ai'],
    events: [chg(0, 80)],
  },
  {
    id: 'boundary-40+40-in-49ms',
    description: '40 + 40 chars 49 ms apart (inside the 50 ms window)',
    expected: ['ai'],
    events: [chg(0, 40), chg(49, 40)],
  },
  {
    id: 'boundary-40+40-in-51ms',
    description: '40 + 40 chars 51 ms apart (outside the 50 ms window)',
    expected: ['human'],
    events: [chg(0, 40), chg(51, 40)],
  },
  {
    id: 'multi-file-switch',
    description: 'typing in a.py, then typing in b.py 100 ms later',
    expected: ['human', 'human'],
    events: [chg(0, 5, { fileKey: 'a.py' }), chg(100, 5, { fileKey: 'b.py' })],
  },
  {
    id: 'multi-file-paste-second',
    description:
      'typing in a.py, then a signalled paste into b.py 100 ms later',
    expected: ['human', 'paste'],
    events: [
      chg(0, 5, { fileKey: 'a.py' }),
      { t: 100, kind: 'paste' },
      chg(100, 25, { fileKey: 'b.py' }),
    ],
    knownFailure:
      'the paste signal is stamped before the file-switch closes a.py, so a.py (within 100 ms) is also tagged paste',
  },
  {
    id: 'multi-file-paste-second-after-gap',
    description: 'same, but the paste lands 300 ms after the a.py keystroke',
    expected: ['human', 'paste'],
    events: [
      chg(0, 5, { fileKey: 'a.py' }),
      { t: 300, kind: 'paste' },
      chg(300, 25, { fileKey: 'b.py' }),
    ],
  },
  lagged('ai-signal-400ms-before', 'aiAccept', 'ai', 600),
  lagged('ai-signal-600ms-before', 'aiAccept', 'ai', 400, AI_LAG),
  lagged('ai-signal-400ms-after', 'aiAccept', 'ai', 1_400),
  lagged('ai-signal-600ms-after', 'aiAccept', 'ai', 1_600, AI_LAG),
  lagged('paste-signal-90ms-before', 'paste', 'paste', 910),
  lagged('paste-signal-110ms-before', 'paste', 'paste', 890, PASTE_LAG),
  lagged('paste-signal-90ms-after', 'paste', 'paste', 1_090),
  lagged('paste-signal-110ms-after', 'paste', 'paste', 1_110, PASTE_LAG),
];

// --------------------------------------------------------------- stuck

const SEC = 1_000;
const sel = (t: number, line: number): StuckEvent => ({
  t: t * SEC,
  kind: 'selection',
  file: 'a.ts',
  line,
});
const scr = (t: number, line: number): StuckEvent => ({
  t: t * SEC,
  kind: 'scroll',
  file: 'a.ts',
  line,
});
const edt = (t: number): StuckEvent => ({
  t: t * SEC,
  kind: 'edit',
  file: 'a.ts',
});
/** Alternating scroll positions 100/140 every `step` s from `from` to `to`. */
const oscillate = (from: number, to: number, step: number): StuckEvent[] => {
  const out: StuckEvent[] = [];
  for (let t = from, i = 0; t <= to; t += step, i++) {
    out.push(scr(t, i % 2 === 0 ? 100 : 140));
  }
  return out;
};
const wander = (from: number, to: number, step: number): StuckEvent[] => {
  const out: StuckEvent[] = [];
  for (let t = from, i = 0; t <= to; t += step, i++) {
    out.push(sel(t, 98 + ((i * 3) % 5)));
  }
  return out;
};

export const STUCK_SCENARIOS: StuckScenario[] = [
  {
    id: 'genuine-dwell',
    description: '150 s within +-6 lines of line 100, faint activity, no edit',
    stuck: true,
    stuckFromMs: 0,
    durationMs: 150 * SEC,
    events: wander(0, 150, 20),
    expectedFires: 1,
  },
  {
    id: 'reading-scrolling',
    description: 'reading down a file: monotonic scroll, cursor follows',
    stuck: false,
    stuckFromMs: 0,
    durationMs: 180 * SEC,
    events: Array.from({ length: 18 }, (_, i) => [
      scr(i * 10, 50 + i * 30),
      ...(i % 2 === 0 ? [sel(i * 10, 50 + i * 30)] : []),
    ]).flat(),
    expectedFires: 0,
  },
  {
    id: 'reading-parked-cursor',
    description:
      'reads by scrolling downward with the caret parked on line 100',
    stuck: false,
    stuckFromMs: 0,
    durationMs: 150 * SEC,
    events: [
      sel(0, 100),
      ...Array.from({ length: 15 }, (_, i) => scr((i + 1) * 10, 100 + i * 30)),
    ],
    expectedFires: 1,
    knownFalseAlarm:
      'dwell keys on caret position only; scrolling while the caret is parked still counts as dwell',
  },
  {
    id: 'scroll-thrash',
    description: 'up/down over the same 40 lines every 6 s, no edit',
    stuck: true,
    stuckFromMs: 10 * SEC,
    durationMs: 90 * SEC,
    events: oscillate(10, 80, 6),
    expectedFires: 1,
  },
  {
    id: 'scroll-below-threshold',
    description: 'two direction flips in a minute (needs 4)',
    stuck: false,
    stuckFromMs: 0,
    durationMs: 100 * SEC,
    events: [100, 140, 100, 140, 180, 220].map((l, i) => scr(50 + i * 6, l)),
    expectedFires: 0,
  },
  {
    id: 'scroll-thrash-while-editing',
    description: 'oscillating scroll but editing every 20 s (progress)',
    stuck: false,
    stuckFromMs: 0,
    durationMs: 120 * SEC,
    events: [
      ...oscillate(0, 110, 6),
      ...Array.from({ length: 6 }, (_, i) => edt(i * 20)),
    ].sort((a, b) => a.t - b.t),
    expectedFires: 0,
  },
  {
    id: 'dwell-interrupted-by-edits',
    description: 'caret parked but an edit every 60 s resets the dwell clock',
    stuck: false,
    stuckFromMs: 0,
    durationMs: 300 * SEC,
    events: [
      sel(0, 100),
      ...Array.from({ length: 5 }, (_, i) => edt((i + 1) * 60 - 5)),
    ],
    expectedFires: 0,
  },
  {
    id: 'idle-gating',
    description: 'one cursor move then 200 s of silence (away from desk)',
    stuck: false,
    stuckFromMs: 0,
    durationMs: 200 * SEC,
    events: [sel(0, 100)],
    expectedFires: 0,
  },
  {
    id: 'cooldown',
    description: 'continuous dwell for 700 s: re-prompts only every 5 min',
    stuck: true,
    stuckFromMs: 0,
    durationMs: 700 * SEC,
    events: wander(0, 700, 20),
    expectedFires: 3,
  },
  {
    id: 'prompt-shown-elsewhere',
    description: 'another prompt shown at 60 s suppresses a dwell for 5 min',
    stuck: true,
    stuckFromMs: 0,
    durationMs: 400 * SEC,
    events: [
      ...wander(0, 400, 20),
      { t: 60 * SEC, kind: 'prompt' as const },
    ].sort((a, b) => a.t - b.t),
    expectedFires: 1,
  },
];
