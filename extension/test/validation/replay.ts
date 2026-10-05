import { mock } from 'node:test';
import { BurstAggregator, DEFAULT_BURST_CONFIG } from '../../src/core/behavior';
import type { EditBurst } from '../../src/core/behavior';
import {
  DEFAULT_STUCK_CONFIG,
  StuckDetector,
} from '../../src/core/stuckDetector';
import { CLOCK_BASE, advanceTo } from '../helpers';
import type { EditScenario, StuckScenario } from './scenarios';
import type { StuckResult } from './metrics';

export interface BurstOutcome {
  id: string;
  index: number;
  expected: string;
  actual: string;
  file: string;
  charsAdded: number;
  durationMs: number;
}

/** Drive one scenario through a fresh aggregator on a mocked clock. */
export function replayEditScenario(s: EditScenario): BurstOutcome[] {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  try {
    const bursts: EditBurst[] = [];
    const a = new BurstAggregator(DEFAULT_BURST_CONFIG, (b) => bursts.push(b));
    a.start();
    for (const e of s.events) {
      advanceTo(CLOCK_BASE + e.t);
      const ts = CLOCK_BASE + e.t;
      if (e.kind === 'aiAccept') a.noteAiAccept(ts);
      else if (e.kind === 'paste') a.notePaste(ts);
      else {
        a.change({
          fileKey: e.fileKey ?? 'src/task.py',
          charsAdded: e.charsAdded,
          charsDeleted: e.charsDeleted ?? 0,
          lines: e.lines ?? 1,
          tsMono: ts,
          undoRedo: e.undoRedo,
        });
      }
    }
    advanceTo(Date.now() + DEFAULT_BURST_CONFIG.gapMs + 500);
    a.flush();
    a.dispose();
    if (bursts.length !== s.expected.length) {
      throw new Error(
        `${s.id}: expected ${s.expected.length} burst(s), got ${bursts.length} burst(s)`,
      );
    }
    return bursts.map((b, index) => ({
      id: s.id,
      index,
      expected: s.expected[index],
      actual: b.origin,
      file: b.file,
      charsAdded: b.charsAdded,
      durationMs: b.durationMs,
    }));
  } finally {
    mock.timers.reset();
  }
}

/** Drive one scenario through a fresh StuckDetector on a mocked clock. */
export function replayStuckScenario(s: StuckScenario): StuckResult & {
  expectedFires: number;
} {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  try {
    const fires: StuckResult['fires'] = [];
    const d = new StuckDetector(DEFAULT_STUCK_CONFIG, (r) =>
      fires.push({ atMs: Date.now() - CLOCK_BASE, reason: r.reason }),
    );
    d.start();
    for (const e of s.events) {
      advanceTo(CLOCK_BASE + e.t);
      if (e.kind === 'prompt') d.notePromptShown();
      else {
        d.signal({
          kind: e.kind,
          file: e.file ?? 'a.ts',
          line: e.line,
          at: Date.now(),
        });
      }
    }
    advanceTo(CLOCK_BASE + s.durationMs);
    d.dispose();
    return {
      id: s.id,
      stuck: s.stuck,
      stuckFromMs: s.stuckFromMs,
      durationMs: s.durationMs,
      fires,
      expectedFires: s.expectedFires,
    };
  } finally {
    mock.timers.reset();
  }
}
