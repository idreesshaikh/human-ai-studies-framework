/**
 * Metric registry for the Data surface (FR-DASH-5).
 *
 * The Data tab used to visualise exactly three static-code metrics; every other
 * measure the study collects was reachable only as a dot on the per-session
 * swimlane (FR-DASH-4). This registry generalises the distribution view: each
 * entry knows how to pull its own observations out of the one-timeline dataset
 * rows (metric rows *and* event rows alike) and declares its measurement type,
 * so the renderer can choose an honest mark for it (NFR-8) instead of forcing
 * every measure through one continuous scale.
 *
 * Pure and dependency-free, like timeline.ts: the component renders what these
 * functions return, and the verify script exercises them directly.
 *
 * Wall: invents no new event shape and no new endpoint. Every row it reads is
 * already join-keyed (participantId, condition, sessionId) and already on the
 * wire from GET /studies/{id}/dataset.
 */

import type { DatasetRow } from "./studyApi";

/** How a measure is distributed, which decides the mark that tells the truth. */
export type MeasurementType = "continuous" | "count" | "ordinal" | "categorical";

/** Which leg a measure comes from — shown as provenance, never color-coded. */
export type MetricOrigin =
  | "static-metrics"
  | "behavioral"
  | "cognitive"
  | "agent"
  | "task";

/** One observation of a metric, already attributed to a participant/condition.
 *  Numeric measures carry `value`; categorical measures carry `category` and an
 *  optional `weight` (e.g. characters) so shares reflect volume, not row count. */
export interface MetricObservation {
  condition: string;
  participantId: string;
  value?: number;
  category?: string;
  weight?: number;
  detail: string;
}

/** A measure the Data surface can plot, and how to read it from dataset rows. */
export interface MetricEntry {
  key: string;
  label: string;
  definition: string;
  measurementType: MeasurementType;
  origin: MetricOrigin;
  /** Research question this previews, when the protocol's plan maps one
   *  (FR-DASH-6: a chart names what it answers). */
  rqId?: string;
  /** Ordered level set for an ordinal measure, e.g. a 1–7 rating. */
  levels?: number[];
  /** Ordered category set for a categorical measure — fixes stack and color
   *  order so a filter never repaints the survivors. Data may add categories
   *  beyond this list; they sort after the declared ones. */
  categories?: string[];
  extract(rows: DatasetRow[]): MetricObservation[];
}

// --------------------------------------------------------------- readers

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function str(v: unknown): string | null {
  return typeof v === "string" && v.length > 0 ? v : null;
}

/** A static-code metric: one numeric field read from every `metrics` row that
 *  carries it. Mirrors the original MetricStrip behaviour exactly. */
function staticMetric(
  key: string,
  label: string,
  definition: string,
  measurementType: "continuous" | "count",
  rqId = "RQ-P2",
): MetricEntry {
  return {
    key,
    label,
    definition,
    measurementType,
    origin: "static-metrics",
    rqId,
    extract(rows) {
      const out: MetricObservation[] = [];
      for (const r of rows) {
        if (r.source !== "metrics") continue;
        const v = num(r.payload[key]);
        if (v === null) continue;
        const fn = str(r.payload.function);
        const file = str(r.payload.file) ?? "?";
        out.push({
          condition: r.condition,
          participantId: r.participantId,
          value: v,
          detail: `${file}${fn ? ` · ${fn}()` : ""} · ${r.participantId}`,
        });
      }
      return out;
    },
  };
}

// --------------------------------------------------------------- the registry

/** The ordered set of measures the Data surface can show. The first three are
 *  the original static metrics, kept first so the panel's default-open metric
 *  is unchanged for a study that only has static-code rows. */
export const METRIC_REGISTRY: MetricEntry[] = [
  staticMetric(
    "cognitive_complexity",
    "Cognitive complexity",
    "A code-structure score: higher values mean more branches, jumps, or nesting to keep track of.",
    "continuous",
  ),
  staticMetric(
    "parameter_count",
    "Function inputs",
    "How many arguments each function accepts.",
    "count",
  ),
  staticMetric(
    "nesting_penalty",
    "Nesting depth",
    "How many layers of ifs and loops sit inside one another.",
    "count",
  ),
  staticMetric(
    "avg_identifier_length",
    "Identifier length",
    "Average length of the names a function introduces — a readability proxy.",
    "continuous",
  ),
  staticMetric(
    "mean_scope_distance",
    "Scope distance (mean)",
    "On average, how far in lines a variable's uses sit from where it is declared.",
    "continuous",
  ),
  staticMetric(
    "max_scope_distance",
    "Scope distance (max)",
    "The widest gap, in lines, between a variable's declaration and a use.",
    "continuous",
  ),
  staticMetric(
    "halstead_effort",
    "Halstead effort",
    "An operator/operand volume estimate of the mental effort to read a function.",
    "continuous",
  ),
  staticMetric(
    "halstead_effort_total",
    "Halstead effort (file)",
    "The same effort estimate totalled across a whole file.",
    "continuous",
  ),
  staticMetric(
    "comment_ratio",
    "Comment ratio",
    "Fraction of a file's lines that are comments.",
    "continuous",
  ),
  staticMetric(
    "indentation_variance",
    "Indentation variance",
    "How uneven a file's indentation is — a rough structural-noise proxy.",
    "continuous",
  ),
  staticMetric(
    "mean_line_width",
    "Mean line width",
    "Average characters per line across a file.",
    "continuous",
  ),
  staticMetric(
    "max_line_width",
    "Max line width",
    "The widest line in a file, in characters.",
    "count",
  ),
  {
    key: "code_authorship",
    label: "Code authorship (AI vs human)",
    definition:
      "Share of added characters by their origin, per condition. Weighted by characters, so it reflects volume written, not the number of edits.",
    measurementType: "categorical",
    origin: "behavioral",
    rqId: "RQ-P3",
    categories: ["ai", "human", "paste", "undo-redo"],
    extract(rows) {
      const out: MetricObservation[] = [];
      for (const r of rows) {
        if (r.type !== "edit_burst") continue;
        const origin = str(r.payload.origin);
        const chars = num(r.payload.charsAdded);
        if (!origin || chars === null || chars <= 0) continue;
        out.push({
          condition: r.condition,
          participantId: r.participantId,
          category: origin,
          weight: chars,
          detail: `${chars} chars (${origin}) · ${r.participantId}`,
        });
      }
      return out;
    },
  },
  {
    key: "edit_lines",
    label: "Lines per edit burst",
    definition:
      "Lines touched in each burst of editing activity. Every burst is one point.",
    measurementType: "count",
    origin: "behavioral",
    rqId: "RQ-P3",
    extract(rows) {
      const out: MetricObservation[] = [];
      for (const r of rows) {
        if (r.type !== "edit_burst") continue;
        const v = num(r.payload.linesTouched);
        if (v === null) continue;
        out.push({
          condition: r.condition,
          participantId: r.participantId,
          value: v,
          detail: `${v} lines · ${r.participantId}`,
        });
      }
      return out;
    },
  },
  {
    key: "fatigue",
    label: "Self-reported fatigue",
    definition:
      "Fatigue logged on a 1–7 scale during the session. Shown as a distribution across levels; an ordinal scale is never averaged.",
    measurementType: "ordinal",
    origin: "cognitive",
    rqId: "RQ-P1",
    levels: [1, 2, 3, 4, 5, 6, 7],
    extract(rows) {
      const out: MetricObservation[] = [];
      for (const r of rows) {
        if (r.type !== "fatigue_response") continue;
        const v = num(r.payload.value);
        if (v === null) continue;
        out.push({
          condition: r.condition,
          participantId: r.participantId,
          value: v,
          detail: `rated ${v} · ${r.participantId}`,
        });
      }
      return out;
    },
  },
  {
    key: "comprehension_correct",
    label: "Comprehension probe correctness",
    definition:
      "Share of in-session comprehension probes answered correctly, per condition. Probes with no gradable answer are dropped.",
    measurementType: "categorical",
    origin: "cognitive",
    rqId: "RQ-P1",
    categories: ["correct", "incorrect"],
    extract(rows) {
      const out: MetricObservation[] = [];
      for (const r of rows) {
        if (r.type !== "comprehension_probe_response") continue;
        const correct = r.payload.correct;
        // `correct` is bool|null: null (ungradable / expired) drops out of a
        // correct-rate rather than being scored as wrong.
        if (correct !== true && correct !== false) continue;
        out.push({
          condition: r.condition,
          participantId: r.participantId,
          category: correct ? "correct" : "incorrect",
          weight: 1,
          detail: `${correct ? "correct" : "incorrect"} · ${r.participantId}`,
        });
      }
      return out;
    },
  },
  {
    key: "ai_char_share",
    label: "AI-authored share",
    definition:
      "Per participant, the share of added characters the AI wrote (origin = ai ÷ all origins). One point per participant.",
    measurementType: "continuous",
    origin: "behavioral",
    rqId: "RQ-P3",
    extract(rows) {
      // Grouped per participant+condition so each point is one developer's
      // session mix, not one edit — the honest unit for a within-subjects share.
      const acc = new Map<
        string,
        { condition: string; participantId: string; ai: number; total: number }
      >();
      for (const r of rows) {
        if (r.type !== "edit_burst") continue;
        const origin = str(r.payload.origin);
        const chars = num(r.payload.charsAdded);
        if (!origin || chars === null || chars <= 0) continue;
        const key = `${r.condition}\u0000${r.participantId}`;
        const e =
          acc.get(key) ??
          { condition: r.condition, participantId: r.participantId, ai: 0, total: 0 };
        e.total += chars;
        if (origin === "ai") e.ai += chars;
        acc.set(key, e);
      }
      const out: MetricObservation[] = [];
      for (const e of acc.values()) {
        if (e.total <= 0) continue;
        const share = e.ai / e.total;
        out.push({
          condition: e.condition,
          participantId: e.participantId,
          value: share,
          detail: `${(share * 100).toFixed(0)}% AI · ${e.participantId}`,
        });
      }
      return out;
    },
  },
  {
    key: "ai_insertion_share",
    label: "AI insertion share (snapshots)",
    definition:
      "Fraction of inserted lines attributable to the AI, computed server-side from workspace snapshots. One point per session.",
    measurementType: "continuous",
    origin: "agent",
    rqId: "RQ-P3",
    extract(rows) {
      const out: MetricObservation[] = [];
      for (const r of rows) {
        if (r.type !== "code_evolution") continue;
        const v = num(r.payload.aiInsertionShare);
        if (v === null) continue;
        out.push({
          condition: r.condition,
          participantId: r.participantId,
          value: v,
          detail: `${(v * 100).toFixed(0)}% AI-inserted · ${r.participantId}`,
        });
      }
      return out;
    },
  },
  {
    key: "agent_latency",
    label: "Agent response latency",
    definition:
      "Milliseconds between a developer turn and the agent's reply. One point per agent turn.",
    measurementType: "continuous",
    origin: "agent",
    rqId: "RQ-P4",
    extract(rows) {
      const out: MetricObservation[] = [];
      for (const r of rows) {
        if (r.type !== "agent_turn") continue;
        const v = num(r.payload.latencyMs);
        if (v === null) continue;
        out.push({
          condition: r.condition,
          participantId: r.participantId,
          value: v,
          detail: `${v} ms · ${r.participantId}`,
        });
      }
      return out;
    },
  },
  {
    key: "task_pass_rate",
    label: "Acceptance-test outcome",
    definition:
      "Share of task-outcome checks that passed, per condition. One observation per recorded task outcome.",
    measurementType: "categorical",
    origin: "task",
    rqId: "RQ-P2",
    categories: ["passed", "failed"],
    extract(rows) {
      const out: MetricObservation[] = [];
      for (const r of rows) {
        if (r.type !== "task_outcome") continue;
        const passed = r.payload.passed;
        if (passed !== true && passed !== false) continue;
        out.push({
          condition: r.condition,
          participantId: r.participantId,
          category: passed ? "passed" : "failed",
          weight: 1,
          detail: `${passed ? "passed" : "failed"} · ${r.participantId}`,
        });
      }
      return out;
    },
  },
];

export function findMetric(key: string): MetricEntry | undefined {
  return METRIC_REGISTRY.find((m) => m.key === key);
}

/** The set of metric keys that actually have at least one observation in these
 *  rows — so the panel can open on a populated measure rather than an empty one. */
export function populatedMetrics(rows: DatasetRow[]): Set<string> {
  const keys = new Set<string>();
  for (const m of METRIC_REGISTRY) {
    if (m.extract(rows).length > 0) keys.add(m.key);
  }
  return keys;
}

// --------------------------------------------------------- aggregation (pure)

export interface Stats {
  n: number;
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
}

/** Five-number summary for a numeric measure. Null for an empty cell so the
 *  caller shows "no data" rather than a fabricated zero. */
export function summarize(values: number[]): Stats | null {
  if (values.length === 0) return null;
  const v = [...values].sort((a, b) => a - b);
  const q = (p: number) => {
    const idx = (v.length - 1) * p;
    const lo = Math.floor(idx);
    return v[lo] + (v[Math.min(lo + 1, v.length - 1)] - v[lo]) * (idx - lo);
  };
  return {
    n: v.length,
    min: v[0],
    q1: q(0.25),
    median: q(0.5),
    q3: q(0.75),
    max: v[v.length - 1],
  };
}

/** Counts per ordinal level for one condition's observations, in `levels` order. */
export function ordinalCounts(
  obs: MetricObservation[],
  levels: number[],
): number[] {
  const counts = levels.map(() => 0);
  for (const o of obs) {
    if (o.value === undefined) continue;
    const i = levels.indexOf(o.value);
    if (i >= 0) counts[i] += 1;
  }
  return counts;
}

export interface CategoryShare {
  category: string;
  weight: number;
  share: number;
}

/** The full, ordered category list present in the data, declared categories
 *  first (in their given order), then any others alphabetically. Keeps color
 *  and stack order stable as conditions are filtered. */
export function categoryOrder(
  obs: MetricObservation[],
  declared: string[] = [],
): string[] {
  const seen = new Set<string>();
  for (const o of obs) if (o.category) seen.add(o.category);
  const order: string[] = [];
  for (const c of declared) if (seen.has(c)) order.push(c);
  const rest = [...seen].filter((c) => !declared.includes(c)).sort();
  return [...order, ...rest];
}

/** Weighted shares per category for one condition's observations, summing to 1
 *  (unless the cell is empty). Weight defaults to 1 per observation. */
export function categoryShares(
  obs: MetricObservation[],
  order: string[],
): { total: number; shares: CategoryShare[] } {
  const weight = new Map<string, number>();
  let total = 0;
  for (const o of obs) {
    if (!o.category) continue;
    const w = o.weight ?? 1;
    weight.set(o.category, (weight.get(o.category) ?? 0) + w);
    total += w;
  }
  const shares = order.map((category) => {
    const w = weight.get(category) ?? 0;
    return { category, weight: w, share: total > 0 ? w / total : 0 };
  });
  return { total, shares };
}
