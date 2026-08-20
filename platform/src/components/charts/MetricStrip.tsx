import { useMemo, useState } from "react";
import { Table2, ChartScatter } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { EmptyState } from "@/components/shell/EmptyState";
import type { DatasetRow } from "@/lib/studyApi";

/* Metric distribution split by condition (FR-DASH-5), small-n honest (NFR-8):
 * every observation is drawn (deterministic jitter), per-cell n is always
 * shown, the quartile box only appears at n ≥ 5, and the table view carries
 * exact summaries. Follows the dataviz skill — thin marks, recessive grid,
 * color follows the entity in fixed slot order, a hover tooltip, and a table
 * alternative so identity is never color-alone. No charting dependency: one
 * linear scale and a quantile helper, hand-built (D17). */

const METRICS: { key: string; label: string; definition: string }[] = [
  {
    key: "cognitive_complexity",
    label: "Cognitive complexity",
    definition:
      "SonarSource's score for how hard a function is to follow (branches, jumps, nesting).",
  },
  {
    key: "parameter_count",
    label: "Parameter count",
    definition: "Arguments per function, against the ~7-item working-memory bound.",
  },
  {
    key: "nesting_penalty",
    label: "Nesting penalty",
    definition:
      "How deeply code nests inside ifs and loops: deeper nesting is harder to hold in your head.",
  },
];

const M = { left: 48, right: 16, top: 12, bottom: 48 };
const H = 300;
const PLOT_W = 720;

interface Stats {
  n: number;
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
}

function summary(values: number[]): Stats | null {
  if (values.length === 0) return null;
  const v = [...values].sort((a, b) => a - b);
  const q = (p: number) => {
    const idx = (v.length - 1) * p;
    const lo = Math.floor(idx);
    return v[lo] + (v[Math.min(lo + 1, v.length - 1)] - v[lo]) * (idx - lo);
  };
  return { n: v.length, min: v[0], q1: q(0.25), median: q(0.5), q3: q(0.75), max: v[v.length - 1] };
}

/** Deterministic jitter — stable across renders, no Math.random. */
function jitter(i: number): number {
  const f = Math.sin((i + 1) * 12.9898) * 43758.5453;
  return (f - Math.floor(f) - 0.5) * 0.55;
}

export function MetricStrip({
  rows,
  conditions,
}: {
  rows: DatasetRow[];
  conditions: string[];
}) {
  const [metricKey, setMetricKey] = useState(METRICS[0].key);
  const [asTable, setAsTable] = useState(false);
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);

  const metric = METRICS.find((m) => m.key === metricKey) ?? METRICS[0];

  const points = useMemo(
    () =>
      rows.flatMap((r) => {
        const v = r.payload[metric.key];
        if (typeof v !== "number" || !Number.isFinite(v)) return [];
        const fn = typeof r.payload.function === "string" ? r.payload.function : null;
        const file = typeof r.payload.file === "string" ? r.payload.file : "?";
        return [
          {
            value: v,
            condition: r.condition,
            detail: `${file}${fn ? ` · ${fn}()` : ""} · ${r.participantId}`,
          },
        ];
      }),
    [rows, metric.key],
  );

  const conds = conditions.length
    ? conditions
    : [...new Set(points.map((p) => p.condition))].sort();

  const byCondition = conds.map((c, i) => {
    const pts = points.filter((p) => p.condition === c);
    return { condition: c, slot: (i % 8) + 1, points: pts, stats: summary(pts.map((p) => p.value)) };
  });

  const plotH = H - M.top - M.bottom;
  const plotW = PLOT_W - M.left - M.right;
  const maxV = points.length ? Math.max(...points.map((p) => p.value)) : 1;
  const minV = Math.min(0, ...(points.length ? points.map((p) => p.value) : [0]));
  const yTop = niceCeil(maxV);
  const y = (v: number) => plotH - ((v - minV) / (yTop - minV || 1)) * plotH;
  const bandW = plotW / Math.max(conds.length, 1);
  const ticks = Array.from({ length: 6 }, (_, i) => minV + ((yTop - minV) * i) / 5);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 type-body text-text-muted">
          Metric
          <Select
            value={metricKey}
            onValueChange={setMetricKey}
            options={METRICS.map((m) => ({ value: m.key, label: m.label }))}
            className="h-8 w-auto"
          />
        </label>
        <Button
          size="sm"
          variant="ghost"
          className="ml-auto type-caption"
          onClick={() => setAsTable((v) => !v)}
        >
          {asTable ? <ChartScatter aria-hidden /> : <Table2 aria-hidden />}
          {asTable ? "Chart" : "Table"}
        </Button>
      </div>
      <p className="type-caption text-text-muted">{metric.definition}</p>

      {/* A stable min-height keeps the section from jumping when the selected
          metric has no rows (short notice) vs. a full chart/table — the
          layout-shift the researcher saw when switching metric/condition. */}
      <div className="min-h-[19rem]">
      {points.length === 0 ? (
        <EmptyState
          line={
            <>
              No metric rows carry{" "}
              <span className="type-quantity identifier">{metric.key}</span> yet.
              Metric rows appear after the metrics tool analyses a session's
              code.
            </>
          }
        />
      ) : asTable ? (
        <div className="overflow-x-auto rounded-card border border-border bg-surface">
          <table className="w-full type-body">
            <thead>
              <tr className="border-b border-border text-left text-text-muted">
                {["Condition", "n", "min", "q1", "median", "q3", "max"].map((h) => (
                  <th key={h} className="px-3 py-2 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="tabular">
              {byCondition.map((c) => (
                <tr key={c.condition} className="border-b border-border last:border-0">
                  <td className="px-3 py-2 text-text">{c.condition}</td>
                  {c.stats ? (
                    <>
                      <td className="px-3 py-2">{c.stats.n}</td>
                      <td className="px-3 py-2">{c.stats.min.toFixed(1)}</td>
                      <td className="px-3 py-2">{c.stats.q1.toFixed(1)}</td>
                      <td className="px-3 py-2">{c.stats.median.toFixed(1)}</td>
                      <td className="px-3 py-2">{c.stats.q3.toFixed(1)}</td>
                      <td className="px-3 py-2">{c.stats.max.toFixed(1)}</td>
                    </>
                  ) : (
                    <>
                      <td className="px-3 py-2">0</td>
                      <td className="px-3 py-2 text-text-muted" colSpan={5}>
                        no data
                      </td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="relative overflow-x-auto rounded-card border border-border bg-surface p-2">
          <svg
            viewBox={`0 0 ${PLOT_W} ${H}`}
            className="h-auto w-full"
            role="img"
            aria-label={`${metric.label} by condition, every point drawn`}
            data-agent="metric-strip"
          >
            <g transform={`translate(${M.left},${M.top})`}>
              {ticks.map((t) => (
                <g key={t} transform={`translate(0,${y(t)})`}>
                  <line x1={0} x2={plotW} stroke="var(--viz-grid)" strokeWidth={1} />
                  <text
                    x={-8}
                    dy="0.32em"
                    textAnchor="end"
                    className="tabular fill-text-muted type-caption"
                  >
                    {t.toFixed(0)}
                  </text>
                </g>
              ))}
              <line x1={0} y1={plotH} x2={plotW} y2={plotH} stroke="var(--viz-axis)" />

              {byCondition.map((c, ci) => {
                const cx = ci * bandW + bandW / 2;
                const color = `var(--series-${c.slot})`;
                return (
                  <g key={c.condition}>
                    {c.stats && c.stats.n >= 5 && (
                      <rect
                        x={cx - bandW * 0.18}
                        y={y(c.stats.q3)}
                        width={bandW * 0.36}
                        height={Math.max(y(c.stats.q1) - y(c.stats.q3), 1)}
                        fill={color}
                        opacity={0.12}
                        rx={3}
                      />
                    )}
                    {c.stats && (
                      <line
                        x1={cx - bandW * 0.22}
                        x2={cx + bandW * 0.22}
                        y1={y(c.stats.median)}
                        y2={y(c.stats.median)}
                        stroke={color}
                        strokeWidth={2}
                      />
                    )}
                    {c.points.map((p, pi) => (
                      <circle
                        key={pi}
                        cx={cx + jitter(pi) * bandW * 0.5}
                        cy={y(p.value)}
                        r={4.5}
                        fill={color}
                        stroke="var(--surface)"
                        strokeWidth={2}
                        onPointerMove={(e) =>
                          setTip({ x: e.clientX + 12, y: e.clientY + 12, text: `${p.value}: ${p.detail}` })
                        }
                        onPointerLeave={() => setTip(null)}
                      />
                    ))}
                    <text
                      x={cx}
                      y={plotH + 18}
                      textAnchor="middle"
                      className="fill-text type-caption font-semibold"
                    >
                      {c.condition}
                    </text>
                    <text
                      x={cx}
                      y={plotH + 34}
                      textAnchor="middle"
                      className="tabular fill-text-muted type-caption"
                    >
                      n = {c.stats?.n ?? 0}
                    </text>
                  </g>
                );
              })}
            </g>
          </svg>
          <p className="px-2 type-caption text-text-muted">
            Every observation plotted · median line
            {points.length >= 5 ? " + interquartile box" : ""} · exact values in
            the table view.
          </p>
        </div>
      )}
      </div>

      {tip && (
        <div
          className="pointer-events-none fixed z-50 rounded-input border border-border-strong bg-surface-raised px-2 py-1 type-caption text-text shadow-sheet"
          style={{ left: tip.x, top: tip.y }}
        >
          {tip.text}
        </div>
      )}
    </div>
  );
}

function niceCeil(v: number): number {
  if (v <= 0) return 1;
  const mag = Math.pow(10, Math.floor(Math.log10(v)));
  return Math.ceil(v / mag) * mag;
}
