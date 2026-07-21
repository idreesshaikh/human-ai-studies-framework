/**
 * Lane-assembly module for the session-timeline swimlane (FR-DASH-4).
 *
 * Pure, testable, no DOM dependencies. Groups events by source into labelled
 * lanes, sorted deterministically by timestamp. Provides a minimal time-to-pixel
 * scale (hand-rolled, matching MetricStrip.tsx's no-dependency pattern).
 *
 * Wall #4: renders exactly the join-keyed rows every leg already emits —
 * invents no new event shape.
 */

/** One event row from the middleware (GET /sessions/{id}/events). */
export interface EventRow {
  v: number;
  ts: string;
  mono: number;
  sessionId: string;
  source: string;
  participantId: string;
  condition: string;
  seq: number;
  type: string;
  payload: Record<string, unknown>;
  flags: string[];
}

/** One lane of the swimlane: a label, a source, and its events sorted by ts. */
export interface Lane {
  /** Human-readable label for this lane (e.g. "Cognitive overlay"). */
  label: string;
  /** The source identifier (e.g. "cognitive-overlay"). */
  source: string;
  /** Events belonging to this lane, sorted by ts, then seq. */
  events: EventRow[];
  /** Total event count in this lane. */
  count: number;
  /** Number of flagged events in this lane. */
  flagged: number;
}

/** Lane colour slot (index into the CSS series vars). */
export interface LaneStyle {
  source: string;
  slot: number;
}

/** Parse an ISO-8601 timestamp to epoch ms, or 0 if invalid. */
export function parseTs(ts: string): number {
  const d = new Date(ts);
  return Number.isFinite(d.getTime()) ? d.getTime() : 0;
}

/** Human-readable lane labels keyed by source. */
const LANE_LABELS: Record<string, string> = {
  "cognitive-overlay": "Cognitive overlay",
  "agent-capture": "Agent interaction",
  "agent-derived": "Agent-derived",
  "workspace-snapshot": "Workspace snapshots",
  "task-harness": "Task harness",
  metrics: "Static metrics",
};

/** Fallback label for unknown sources. */
function laneLabel(source: string): string {
  return LANE_LABELS[source] ?? source;
}

/** Lane ordering: known sources first, then alphabetically. */
const LANE_ORDER: Record<string, number> = {
  "cognitive-overlay": 0,
  "agent-capture": 1,
  "agent-derived": 2,
  "workspace-snapshot": 3,
  "task-harness": 4,
  metrics: 5,
};

function laneRank(source: string): number {
  return LANE_ORDER[source] ?? 99;
}

/**
 * Group events into lanes by source. Deterministic: same input → same output.
 * Events within each lane are sorted by ts (then seq for ties).
 */
export function assembleLanes(events: EventRow[]): Lane[] {
  const grouped = new Map<string, EventRow[]>();
  for (const ev of events) {
    const list = grouped.get(ev.source);
    if (list) list.push(ev);
    else grouped.set(ev.source, [ev]);
  }

  const lanes: Lane[] = [];
  for (const [source, evs] of grouped) {
    evs.sort((a, b) => {
      const tA = parseTs(a.ts);
      const tB = parseTs(b.ts);
      return tA - tB || a.seq - b.seq;
    });
    lanes.push({
      label: laneLabel(source),
      source,
      events: evs,
      count: evs.length,
      flagged: evs.filter((e) => e.flags.length > 0).length,
    });
  }

  // Sort lanes: known sources first (per LANE_ORDER), then alphabetically.
  lanes.sort((a, b) => {
    const ra = laneRank(a.source);
    const rb = laneRank(b.source);
    return ra - rb || a.source.localeCompare(b.source);
  });

  return lanes;
}

/**
 * Build a linear time-to-pixel scale function.
 *
 * Returns a function mapping an ISO-8601 timestamp string to an x-position in
 * pixels within [0, width]. Handles the empty/single-event edge case without
 * dividing by zero.
 */
export function timeScale(
  events: EventRow[],
  width: number,
  marginLeft: number = 60,
  marginRight: number = 20,
): (ts: string) => number {
  const plotW = width - marginLeft - marginRight;
  if (events.length === 0) {
    return () => marginLeft;
  }

  let minTs = Infinity;
  let maxTs = -Infinity;
  for (const ev of events) {
    const t = parseTs(ev.ts);
    if (t < minTs) minTs = t;
    if (t > maxTs) maxTs = t;
  }

  // Single event or all same timestamp: centre it.
  const range = maxTs - minTs;
  if (range === 0) {
    const centre = marginLeft + plotW / 2;
    return () => centre;
  }

  return (ts: string) => {
    const t = parseTs(ts);
    const frac = (t - minTs) / range;
    return marginLeft + frac * plotW;
  };
}

/**
 * Lane colouring: deterministic slot per source for visual consistency
 * across re-renders. 8 slots in the validated palette.
 */
export function laneStyle(source: string): LaneStyle {
  const HASH_SLOTS = [
    1, 3, 5, 7, 2, 4, 6, 8,
  ];
  let hash = 0;
  for (let i = 0; i < source.length; i++) {
    hash = (hash * 31 + source.charCodeAt(i)) | 0;
  }
  return { source, slot: HASH_SLOTS[((hash & 0x7fffffff) % HASH_SLOTS.length)] };
}
