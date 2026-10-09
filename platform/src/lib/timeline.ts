/* Group joined session events into timestamp-ordered source lanes. */

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
  /** Human-readable label for this lane (e.g. "Editor capture"). */
  label: string;
  /** The source identifier (e.g. "tern"). */
  source: string;
  /** Events belonging to this lane, sorted by ts, then seq. */
  events: EventRow[];
  /** Total event count in this lane. */
  count: number;
  /** Number of flagged events in this lane. */
  flagged: number;
}

/** Parse an ISO-8601 timestamp to epoch ms, or 0 if invalid. */
export function parseTs(ts: string): number {
  const d = new Date(ts);
  return Number.isFinite(d.getTime()) ? d.getTime() : 0;
}

/** Human-readable lane labels keyed by source. */
const LANE_LABELS: Record<string, string> = {
  tern: "Editor capture",
  // Rows written before the stream was renamed. New events are normalised at
  // ingest, but a database that predates the rename still holds the old value
  // and an unlabelled lane would read as an unknown producer.
  "cognitive-overlay": "Editor capture",
  "agent-capture": "Agent interaction",
  "agent-derived": "Agent-derived",
  "workspace-snapshot": "Workspace snapshots",
  "task-harness": "Task harness",
  metrics: "Static metrics",
};

/** Fallback label for unknown sources. */
export function laneLabel(source: string): string {
  return LANE_LABELS[source] ?? source;
}

/** Lane ordering: known sources first, then alphabetically. */
const LANE_ORDER: Record<string, number> = {
  tern: 0,
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
