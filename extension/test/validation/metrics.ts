export interface LabelledPair {
  id: string;
  index: number;
  expected: string;
  actual: string;
}

/** Rows are the expected label, columns the actual one. */
export function confusionMatrix(
  pairs: LabelledPair[],
  labels: string[],
): number[][] {
  const m = labels.map(() => labels.map(() => 0));
  for (const p of pairs) {
    const e = labels.indexOf(p.expected);
    const a = labels.indexOf(p.actual);
    if (e >= 0 && a >= 0) m[e][a]++;
  }
  return m;
}

export interface ClassStat {
  label: string;
  /** null when the class was never predicted. */
  precision: number | null;
  /** null when the class has no ground-truth support. */
  recall: number | null;
  support: number;
}

export function classStats(m: number[][], labels: string[]): ClassStat[] {
  return labels.map((label, i) => {
    const support = m[i].reduce((s, n) => s + n, 0);
    const predicted = m.reduce((s, row) => s + row[i], 0);
    return {
      label,
      precision: predicted ? m[i][i] / predicted : null,
      recall: support ? m[i][i] / support : null,
      support,
    };
  });
}

export function misclassified(pairs: LabelledPair[]): LabelledPair[] {
  return pairs.filter((p) => p.expected !== p.actual);
}

export interface StuckResult {
  id: string;
  stuck: boolean;
  stuckFromMs: number;
  durationMs: number;
  fires: { atMs: number; reason: string }[];
}

export interface StuckSummary {
  stuckScenarios: number;
  detected: number;
  /** Per detected stuck scenario: first fire minus stuck onset. */
  timeToDetectMs: number[];
  falseAlarms: number;
  nonStuckHours: number;
  falseAlarmsPerHour: number | null;
}

export function summariseStuck(results: StuckResult[]): StuckSummary {
  const stuck = results.filter((r) => r.stuck);
  const calm = results.filter((r) => !r.stuck);
  const timeToDetectMs = stuck
    .filter((r) => r.fires.length > 0)
    .map((r) => r.fires[0].atMs - r.stuckFromMs);
  const falseAlarms = calm.reduce((s, r) => s + r.fires.length, 0);
  const nonStuckHours = calm.reduce((s, r) => s + r.durationMs, 0) / 3_600_000;
  return {
    stuckScenarios: stuck.length,
    detected: timeToDetectMs.length,
    timeToDetectMs,
    falseAlarms,
    nonStuckHours,
    falseAlarmsPerHour: nonStuckHours ? falseAlarms / nonStuckHours : null,
  };
}
