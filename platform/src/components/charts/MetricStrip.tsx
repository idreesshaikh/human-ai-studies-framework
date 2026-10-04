import { useMemo, useState } from "react";
import { Table2, ChartScatter } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { EmptyState } from "@/components/shell/EmptyState";
import type { DatasetRow } from "@/lib/studyApi";
import {
  METRIC_REGISTRY,
  findMetric,
  populatedMetrics,
  summarize,
  ordinalCounts,
  categoryOrder,
  categoryShares,
  type MetricEntry,
  type MetricObservation,
} from "@/lib/metricRegistry";

/* Metric distribution split by condition (FR-DASH-5), small-n honest (NFR-8).
 * One panel, three marks chosen by the measure's type so each reads truthfully
 * (the swimlane-only measures of FR-DASH-4 get a real distribution here):
 *   - continuous / count → every observation drawn (deterministic jitter),
 *     median line, IQR box only at n ≥ 5;
 *   - ordinal → counts per level, clustered by condition, never averaged;
 *   - categorical → a per-condition share bar, weighted, with its n.
 * Every mark keeps a table twin with exact numbers, per-cell n always shown,
 * and identity is never carried by color alone. Follows the dataviz skill;
 * no charting dependency — hand-built scales, reading the registry's pure
 * aggregation helpers (D17). */

const M = { left: 48, right: 16, top: 12, bottom: 48 };
const H = 300;
const PLOT_W = 720;

type Tip = { x: number; y: number; text: string } | null;

function useTip() {
  const [tip, setTip] = useState<Tip>(null);
  return {
    tip,
    show: (e: { clientX: number; clientY: number }, text: string) =>
      setTip({ x: e.clientX + 12, y: e.clientY + 12, text }),
    hide: () => setTip(null),
  };
}

function Tooltip({ tip }: { tip: Tip }) {
  if (!tip) return null;
  return (
    <div
      className="pointer-events-none fixed z-50 rounded-input border border-border-strong bg-surface-raised px-2 py-1 type-caption text-text shadow-sheet"
      style={{ left: tip.x, top: tip.y }}
    >
      {tip.text}
    </div>
  );
}

export function MetricStrip({
  rows,
  conditions,
}: {
  rows: DatasetRow[];
  conditions: string[];
}) {
  // `null` means "nobody has chosen yet" — not "no metric". An explicit choice
  // always wins; until there is one, the panel opens on a metric that actually
  // has rows (the first static metric, when a study only captured those).
  const [chosen, setChosen] = useState<string | null>(null);
  const [asTable, setAsTable] = useState(false);

  const populated = useMemo(() => populatedMetrics(rows), [rows]);

  const metricKey =
    chosen ??
    METRIC_REGISTRY.find((m) => populated.has(m.key))?.key ??
    METRIC_REGISTRY[0].key;
  const metric = findMetric(metricKey) ?? METRIC_REGISTRY[0];

  const obs = useMemo(() => metric.extract(rows), [metric, rows]);

  const conds = conditions.length
    ? conditions
    : [...new Set(obs.map((o) => o.condition))].sort();

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 type-body text-text-muted">
          Metric
          <Select
            value={metricKey}
            onValueChange={setChosen}
            options={METRIC_REGISTRY.map((m) => ({ value: m.key, label: m.label }))}
            className="h-8 w-auto"
            aria-label="Choose a measure to plot"
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
      <p className="type-caption text-text-muted">
        {metric.definition}
        {metric.rqId && <span className="ml-1"> · previews {metric.rqId}</span>}
      </p>

      {/* Full chart/table states keep a stable working height, while an empty
          metric stays content-sized. */}
      <div className={obs.length === 0 ? "" : "min-h-[19rem]"}>
        {obs.length === 0 ? (
          <EmptyState
            line={
              <>
                No measurements for{" "}
                <span className="font-medium text-text">{metric.label}</span> yet.
                Choose another measure above, or collect a session that produces
                it.
              </>
            }
          />
        ) : (
          <MetricView metric={metric} obs={obs} conds={conds} asTable={asTable} />
        )}
      </div>
    </div>
  );
}

function MetricView({
  metric,
  obs,
  conds,
  asTable,
}: {
  metric: MetricEntry;
  obs: MetricObservation[];
  conds: string[];
  asTable: boolean;
}) {
  switch (metric.measurementType) {
    case "ordinal":
      return <OrdinalDistribution metric={metric} obs={obs} conds={conds} asTable={asTable} />;
    case "categorical":
      return <CategoricalShare metric={metric} obs={obs} conds={conds} asTable={asTable} />;
    default:
      return <PointStrip metric={metric} obs={obs} conds={conds} asTable={asTable} />;
  }
}

// ----------------------------------------------------- continuous & count

/** Deterministic jitter — stable across renders, no Math.random. */
function jitter(i: number): number {
  const f = Math.sin((i + 1) * 12.9898) * 43758.5453;
  return (f - Math.floor(f) - 0.5) * 0.55;
}

function PointStrip({
  metric,
  obs,
  conds,
  asTable,
}: {
  metric: MetricEntry;
  obs: MetricObservation[];
  conds: string[];
  asTable: boolean;
}) {
  const { tip, show, hide } = useTip();

  const points = obs
    .filter((o) => o.value !== undefined)
    .map((o) => ({ value: o.value as number, condition: o.condition, detail: o.detail }));

  const byCondition = conds.map((c, i) => {
    const pts = points.filter((p) => p.condition === c);
    return { condition: c, slot: (i % 8) + 1, points: pts, stats: summarize(pts.map((p) => p.value)) };
  });

  const plotH = H - M.top - M.bottom;
  const plotW = PLOT_W - M.left - M.right;
  const maxV = points.length ? Math.max(...points.map((p) => p.value)) : 1;
  const minV = Math.min(0, ...(points.length ? points.map((p) => p.value) : [0]));
  const yTop = niceCeil(maxV);
  const y = (v: number) => plotH - ((v - minV) / (yTop - minV || 1)) * plotH;
  const bandW = plotW / Math.max(conds.length, 1);
  const ticks = Array.from({ length: 6 }, (_, i) => minV + ((yTop - minV) * i) / 5);

  if (asTable) {
    return (
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
                <td className="px-3 py-2 text-text">{conditionLabel(c.condition)}</td>
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
    );
  }

  return (
    <div className="relative overflow-x-auto rounded-card border border-border bg-surface p-2">
      <svg
        viewBox={`0 0 ${PLOT_W} ${H}`}
        className="h-auto w-full"
        role="img"
        aria-label={`${metric.label} by condition, every observation drawn`}
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
                    onPointerMove={(e) => show(e, `${p.value}: ${p.detail}`)}
                    onPointerLeave={hide}
                  />
                ))}
                <text
                  x={cx}
                  y={plotH + 18}
                  textAnchor="middle"
                  className="fill-text type-caption font-semibold"
                >
                  {conditionLabel(c.condition)}
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
        {points.length >= 5 ? " + interquartile box" : ""} · exact values in the
        table view.
      </p>
      <Tooltip tip={tip} />
    </div>
  );
}

// ------------------------------------------------------------- ordinal

function OrdinalDistribution({
  metric,
  obs,
  conds,
  asTable,
}: {
  metric: MetricEntry;
  obs: MetricObservation[];
  conds: string[];
  asTable: boolean;
}) {
  const { tip, show, hide } = useTip();
  const levels =
    metric.levels ??
    [...new Set(obs.map((o) => o.value).filter((v): v is number => v !== undefined))].sort(
      (a, b) => a - b,
    );

  const byCondition = conds.map((c, i) => {
    const cObs = obs.filter((o) => o.condition === c);
    const counts = ordinalCounts(cObs, levels);
    return { condition: c, slot: (i % 8) + 1, counts, n: counts.reduce((a, b) => a + b, 0) };
  });

  if (asTable) {
    return (
      <div className="overflow-x-auto rounded-card border border-border bg-surface">
        <table className="w-full type-body">
          <thead>
            <tr className="border-b border-border text-left text-text-muted">
              <th className="px-3 py-2 font-medium">Level</th>
              {byCondition.map((c) => (
                <th key={c.condition} className="px-3 py-2 font-medium">
                  {conditionLabel(c.condition)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="tabular">
            {levels.map((lvl, li) => (
              <tr key={lvl} className="border-b border-border last:border-0">
                <td className="px-3 py-2 text-text">{lvl}</td>
                {byCondition.map((c) => (
                  <td key={c.condition} className="px-3 py-2">
                    {c.counts[li]}
                  </td>
                ))}
              </tr>
            ))}
            <tr className="border-t border-border-strong">
              <td className="px-3 py-2 text-text-muted">n</td>
              {byCondition.map((c) => (
                <td key={c.condition} className="px-3 py-2 text-text-muted">
                  {c.n}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    );
  }

  const plotH = H - M.top - M.bottom;
  const plotW = PLOT_W - M.left - M.right;
  const maxCount = Math.max(1, ...byCondition.flatMap((c) => c.counts));
  const yTop = niceCeil(maxCount);
  const y = (v: number) => plotH - (v / (yTop || 1)) * plotH;
  const groupW = plotW / levels.length;
  const nSeries = Math.max(byCondition.length, 1);
  const barSlot = (groupW * 0.72) / nSeries;
  const ticks = Array.from({ length: 6 }, (_, i) => (yTop * i) / 5);

  return (
    <div className="flex flex-col gap-2">
      <Legend items={byCondition.map((c) => ({ label: conditionLabel(c.condition), slot: c.slot, n: c.n }))} />
      <div className="relative overflow-x-auto rounded-card border border-border bg-surface p-2">
        <svg
          viewBox={`0 0 ${PLOT_W} ${H}`}
          className="h-auto w-full"
          role="img"
          aria-label={`${metric.label}: count per level, clustered by condition`}
        >
          <g transform={`translate(${M.left},${M.top})`}>
            {ticks.map((t) => (
              <g key={t} transform={`translate(0,${y(t)})`}>
                <line x1={0} x2={plotW} stroke="var(--viz-grid)" strokeWidth={1} />
                <text x={-8} dy="0.32em" textAnchor="end" className="tabular fill-text-muted type-caption">
                  {t.toFixed(0)}
                </text>
              </g>
            ))}
            <line x1={0} y1={plotH} x2={plotW} y2={plotH} stroke="var(--viz-axis)" />

            {levels.map((lvl, li) => {
              const gx = li * groupW + groupW * 0.14;
              return (
                <g key={lvl}>
                  {byCondition.map((c, ci) => {
                    const count = c.counts[li];
                    const x = gx + ci * barSlot;
                    const h = plotH - y(count);
                    return (
                      <rect
                        key={c.condition}
                        x={x}
                        y={y(count)}
                        width={Math.max(barSlot - 2, 1)}
                        height={Math.max(h, count > 0 ? 1 : 0)}
                        fill={`var(--series-${c.slot})`}
                        rx={2}
                        onPointerMove={(e) =>
                          show(e, `${conditionLabel(c.condition)} · level ${lvl}: ${count}`)
                        }
                        onPointerLeave={hide}
                      />
                    );
                  })}
                  <text
                    x={li * groupW + groupW / 2}
                    y={plotH + 18}
                    textAnchor="middle"
                    className="tabular fill-text type-caption"
                  >
                    {lvl}
                  </text>
                </g>
              );
            })}
            <text
              x={plotW / 2}
              y={plotH + 36}
              textAnchor="middle"
              className="fill-text-muted type-caption"
            >
              rating level
            </text>
          </g>
        </svg>
        <p className="px-2 type-caption text-text-muted">
          Counts per level — an ordinal scale is shown as a distribution, never
          averaged. Exact counts in the table view.
        </p>
        <Tooltip tip={tip} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------- categorical

function CategoricalShare({
  metric,
  obs,
  conds,
  asTable,
}: {
  metric: MetricEntry;
  obs: MetricObservation[];
  conds: string[];
  asTable: boolean;
}) {
  const { tip, show, hide } = useTip();
  const order = categoryOrder(obs, metric.categories ?? []);

  const byCondition = conds.map((c) => {
    const cObs = obs.filter((o) => o.condition === c);
    const { total, shares } = categoryShares(cObs, order);
    return { condition: c, total, shares };
  });

  const slotOf = (category: string) => ((order.indexOf(category) % 8) + 8) % 8 + 1;

  if (asTable) {
    return (
      <div className="overflow-x-auto rounded-card border border-border bg-surface">
        <table className="w-full type-body">
          <thead>
            <tr className="border-b border-border text-left text-text-muted">
              <th className="px-3 py-2 font-medium">Condition</th>
              {order.map((cat) => (
                <th key={cat} className="px-3 py-2 font-medium">
                  {cat}
                </th>
              ))}
              <th className="px-3 py-2 font-medium">n</th>
            </tr>
          </thead>
          <tbody className="tabular">
            {byCondition.map((c) => (
              <tr key={c.condition} className="border-b border-border last:border-0">
                <td className="px-3 py-2 text-text">{conditionLabel(c.condition)}</td>
                {c.shares.map((s) => (
                  <td key={s.category} className="px-3 py-2">
                    {(s.share * 100).toFixed(0)}% ({s.weight})
                  </td>
                ))}
                <td className="px-3 py-2 text-text-muted">{c.total}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <Legend items={order.map((cat) => ({ label: cat, slot: slotOf(cat) }))} />
      <div className="relative flex flex-col gap-3 rounded-card border border-border bg-surface p-3">
        {byCondition.map((c) => (
          <div key={c.condition} className="flex flex-col gap-1">
            <div className="flex items-baseline justify-between type-caption">
              <span className="font-semibold text-text">{conditionLabel(c.condition)}</span>
              <span className="tabular text-text-muted">n = {c.total}</span>
            </div>
            {c.total === 0 ? (
              <p className="type-caption text-text-muted">no data</p>
            ) : (
              <div
                className="flex h-6 w-full gap-0.5 overflow-hidden rounded-input"
                role="img"
                aria-label={`${conditionLabel(c.condition)}: ${c.shares
                  .filter((s) => s.weight > 0)
                  .map((s) => `${(s.share * 100).toFixed(0)}% ${s.category}`)
                  .join(", ")}`}
              >
                {c.shares
                  .filter((s) => s.weight > 0)
                  .map((s) => (
                    <div
                      key={s.category}
                      style={{ width: `${s.share * 100}%`, background: `var(--series-${slotOf(s.category)})` }}
                      onPointerMove={(e) =>
                        show(
                          e,
                          `${conditionLabel(c.condition)} · ${s.category}: ${(s.share * 100).toFixed(0)}% (${s.weight})`,
                        )
                      }
                      onPointerLeave={hide}
                    />
                  ))}
              </div>
            )}
          </div>
        ))}
        <p className="type-caption text-text-muted">
          Shares are weighted by volume; exact counts in the table view.
        </p>
        <Tooltip tip={tip} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- shared

function Legend({
  items,
}: {
  items: { label: string; slot: number; n?: number }[];
}) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1">
      {items.map((it) => (
        <li key={it.label} className="flex items-center gap-1.5 type-caption text-text-muted">
          <span
            className="inline-block size-2.5 rounded-chip"
            style={{ background: `var(--series-${it.slot})` }}
            aria-hidden
          />
          <span className="text-text">{it.label}</span>
          {it.n !== undefined && <span className="tabular">n = {it.n}</span>}
        </li>
      ))}
    </ul>
  );
}

function niceCeil(v: number): number {
  if (v <= 0) return 1;
  const mag = Math.pow(10, Math.floor(Math.log10(v)));
  return Math.ceil(v / mag) * mag;
}

function conditionLabel(value: string): string {
  return value
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
