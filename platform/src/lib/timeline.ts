

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

export interface Lane {

  label: string;

  source: string;

  events: EventRow[];

  count: number;

  flagged: number;
}

export interface LaneStyle {
  source: string;
  slot: number;
}

export function parseTs(ts: string): number {
  const d = new Date(ts);
  return Number.isFinite(d.getTime()) ? d.getTime() : 0;
}

const LANE_LABELS: Record<string, string> = {
  tern: "TERN editor",

  "cognitive-overlay": "TERN editor",
  "agent-capture": "Agent interaction",
  "agent-derived": "Agent-derived",
  "workspace-snapshot": "Workspace snapshots",
  "task-harness": "Task harness",
  metrics: "Static metrics",
};

function laneLabel(source: string): string {
  return LANE_LABELS[source] ?? source;
}

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

  lanes.sort((a, b) => {
    const ra = laneRank(a.source);
    const rb = laneRank(b.source);
    return ra - rb || a.source.localeCompare(b.source);
  });

  return lanes;
}

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
