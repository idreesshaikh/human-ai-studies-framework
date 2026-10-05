import type { EditOrigin } from '../../src/core/behavior';
import type { EditEvent, EditScenario } from './scenarios';

/**
 * Optional labelled real-session recording (see docs/validation.md).
 * `events` is the exported signal log (offsets in ms from the first event),
 * `labels` the human-assigned origin of each burst, in order.
 */
export interface RealSessionRecording {
  version: 1;
  source?: string;
  events: EditEvent[];
  labels: EditOrigin[];
}

const ORIGINS: readonly string[] = ['human', 'ai', 'paste', 'undo-redo'];

export function parseRecording(text: string): EditScenario {
  const r = JSON.parse(text) as Partial<RealSessionRecording>;
  if (r.version !== 1) throw new Error('recording: unsupported version');
  if (!Array.isArray(r.events) || !Array.isArray(r.labels)) {
    throw new Error('recording: events and labels must be arrays');
  }
  for (const l of r.labels) {
    if (!ORIGINS.includes(l)) throw new Error(`recording: bad label ${l}`);
  }
  let prev = 0;
  for (const e of r.events) {
    const ok =
      typeof e.t === 'number' &&
      e.t >= prev &&
      (e.kind === 'aiAccept' ||
        e.kind === 'paste' ||
        (e.kind === 'change' && typeof e.charsAdded === 'number'));
    if (!ok) throw new Error('recording: malformed or unordered event');
    prev = e.t;
  }
  return {
    id: 'real-session',
    description: `labelled recording${r.source ? ` (${r.source})` : ''}`,
    expected: r.labels,
    events: r.events,
  };
}
