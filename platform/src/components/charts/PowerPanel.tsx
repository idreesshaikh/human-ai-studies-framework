import { useCallback, useEffect, useState } from "react";
import { Crosshair } from "lucide-react";
import { Surface } from "@/components/shell/Surface";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/cn";
import { studyApi, onSeededData } from "@/lib/studyApi";
import type { PowerDoc, PowerRequirement } from "@/lib/types";

/* The Planning surface (P2-2): the power/sensitivity curve for the study's
 * planned comparison  -  how power moves with total n, and the first n that
 * reaches the target, per effect size. Planning math only, from the
 * middleware's /studies/{id}/power: the payload carries its own model and
 * assumptions, and a target not reached within the explored range is
 * reported as such, never as a number. Nothing here animates  -  the numbers
 * are the point. */
const SVG_W = 840;
const M = { left: 56, right: 24, top: 16, bottom: 36 };
const PLOT_H = 300;
const LINE_COLORS = [
  "var(--series-1)",
  "var(--series-3)",
  "var(--series-5)",
  "var(--series-7)",
];

/* A stroke pattern per series, carried everywhere the series appears.
 *
 * tokens.css commits this world to it in as many words  -  "every series that
 * must survive a greyscale print carries a mark as well as a hue"  -  and the
 * curve was the one place that didn't: three solid 1.6px lines separated by
 * colour alone, which is also the exactly the reading a red-green viewer, a
 * greyscale print of a thesis chapter, or a projector with the saturation
 * crushed does not get. */
const LINE_DASHES = ["", "7 3", "2 3", "9 3 2 3"];

const ALPHAS = [0.01, 0.05, 0.1];
const TARGETS = [0.8, 0.9];
const MAX_NS = [60, 120, 200, 400];
const SIZES = [0.2, 0.5, 0.8];

/* A series' identity is its EFFECT SIZE, not its position in the response.
 * Keyed by position in `doc.curves`, deselecting d=0.2 promoted d=0.5 into
 * slot 0 and the pink curve silently turned blue  -  the same quantity drawn
 * in the colour that had meant a different one a moment earlier, which is
 * the one thing a planning chart must never do. */
function seriesOf(effectSize: number): { color: string; dash: string } {
  const i = SIZES.indexOf(effectSize);
  const k = i >= 0 ? i : LINE_COLORS.length - 1;
  return { color: LINE_COLORS[k], dash: LINE_DASHES[k] };
}

export function PowerPanel({ studyId }: { studyId: string }) {
  const [alpha, setAlpha] = useState(0.05);
  const [powerTarget, setPowerTarget] = useState(0.8);
  const [maxN, setMaxN] = useState(120);
  const [sizes, setSizes] = useState<number[]>([0.2, 0.5, 0.8]);
  const [doc, setDoc] = useState<PowerDoc | null>(null);
  const [loading, setLoading] = useState(true);
  const [seeded, setSeeded] = useState(false);

  const load = useCallback(
    (live: boolean) => {
      setLoading(true);
      studyApi
        .power(studyId, { alpha, powerTarget, maxN, effectSizes: sizes })
        .then((d) => {
          if (live) setDoc(d);
        })
        .catch(() => {
          if (live) setDoc(null);
        })
        .finally(() => {
          if (live) setLoading(false);
        });
    },
    [studyId, alpha, powerTarget, maxN, sizes],
  );

  useEffect(() => {
    // If the read falls back to the built-in stand-in, say so honestly.
    const off = onSeededData(() => setSeeded(true));
    let live = true;
    load(live);
    return () => {
      live = false;
      off();
    };
  }, [load]);

  const toggleSize = (d: number) =>
    setSizes((prev) =>
      prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d].sort(),
    );

  return (
    <Surface measure="work" label="Planning">
      <section className="flex flex-col gap-stack">
        <div className="flex flex-col gap-1">
          <h2 className="type-section text-text">Recruitment planning</h2>
          <p className="type-body text-text-muted">
            Power for the planned comparison, before any participant. The
            curve is planning math, not a result  -  the model and its
            assumptions are stated with the numbers.
          </p>
        </div>

        {loading && doc === null ? (
          <div className="rounded-card border border-dashed border-border-strong bg-surface p-5">
            <p className="type-body text-text-muted">Loading the study plan…</p>
          </div>
        ) : doc?.note ? (
          <div className="rounded-card border border-dashed border-border-strong bg-surface p-5">
            <p className="type-body text-text">{doc.note}</p>
            <p className="mt-2 type-caption text-text-muted">
              The chart will appear once Phoenix has a real comparison to size.
            </p>
          </div>
        ) : (
          <>

        {/* Controls: alpha, target, explored range, effect sizes. Every
            change refetches the exact curve from the middleware. */}
        <div className="flex flex-wrap items-end gap-4 rounded-card border border-border bg-surface p-4">
          <label className="flex flex-col gap-1">
            <span className="type-caption text-text-muted">alpha (two-sided)</span>
            <Select
              value={String(alpha)}
              onValueChange={(v) => setAlpha(Number(v))}
              options={ALPHAS.map((a) => ({ value: String(a), label: String(a) }))}
              className="w-28"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="type-caption text-text-muted">target power</span>
            <Select
              value={String(powerTarget)}
              onValueChange={(v) => setPowerTarget(Number(v))}
              options={TARGETS.map((t) => ({ value: String(t), label: `${t * 100}%` }))}
              className="w-28"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="type-caption text-text-muted">explored range (total n)</span>
            <Select
              value={String(maxN)}
              onValueChange={(v) => setMaxN(Number(v))}
              options={MAX_NS.map((n) => ({ value: String(n), label: `up to ${n}` }))}
              className="w-32"
            />
          </label>
          <div className="flex flex-col gap-1">
            <span className="type-caption text-text-muted">effect sizes (Cohen's d)</span>
            {/* These are the chart's legend, and they happen to be
              * switchable  -  so each one carries the stroke its curve is drawn
              * with, and you can read the key off the control rather than
              * matching two colours across the panel.
              *
              * They are emphatically NOT accent. Selected used to mean
              * `border-accent`, which put three accent-edged controls in a
              * row directly above an accent-free chart: in this world a fill
              * or an edge in the accent means "an action you can take", and
              * a size you have already switched on is a state, not an action
              *  -  the exact "two things both meaning primary" failure
              * tokens.css says this palette exists to end. On is a raised
              * plate with a strong edge and its own series mark; off is flat
              * paper with the mark drained out of it. */}
            <div className="flex gap-2">
              {SIZES.map((d) => {
                const on = sizes.includes(d);
                const { color, dash } = seriesOf(d);
                return (
                  <button
                    key={d}
                    type="button"
                    aria-pressed={on}
                    onClick={() => toggleSize(d)}
                    className={cn(
                      "flex h-10 items-center gap-2 rounded-input border px-3 type-body transition-colors duration-fast",
                      on
                        ? "border-border-strong bg-surface-raised text-text shadow-mark"
                        : "border-border bg-surface text-text-muted hover:border-border-strong hover:text-text",
                    )}
                  >
                    <svg
                      width={16}
                      height={2}
                      viewBox="0 0 16 2"
                      aria-hidden
                      className="shrink-0 overflow-visible"
                    >
                      <line
                        x1={0}
                        y1={1}
                        x2={16}
                        y2={1}
                        stroke={on ? color : "var(--border-strong)"}
                        strokeWidth={1.6}
                        strokeDasharray={dash || undefined}
                      />
                    </svg>
                    d={d}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {seeded && (
          <p className="type-caption text-text-muted" role="status">
            Middleware unreachable  -  showing the built-in stand-in curve
            (normal approximation of the same formula), not a live study
            plan.
          </p>
        )}

        {doc === null ? (
          <div className="rounded-card border border-border bg-surface p-4">
            <p className="type-body text-text-muted">
              The planning curve is unavailable right now.
            </p>
          </div>
        ) : sizes.length === 0 ? (
          <div className="rounded-card border border-border bg-surface p-4">
            <p className="type-body text-text-muted">
              Nothing to draw  -  select at least one effect size.
            </p>
          </div>
        ) : doc.curves.length === 0 ? (
          <div className="rounded-card border border-border bg-surface p-4">
            <p className="type-body text-text-muted">
              The planning curve is unavailable right now.
            </p>
          </div>
        ) : (
          <>
            <PowerChart doc={doc} />
            <RequiredTable
              requirements={doc.requiredN}
              maxTotalN={doc.maxTotalN}
              paired={doc.model.startsWith("paired")}
            />
            <p className="type-caption text-text-muted">
              Model: {doc.model}. alpha = {doc.alpha}, target ={" "}
              {doc.powerTarget * 100}%, range explored up to total n ={" "}
               {doc.maxTotalN}. {doc.model.startsWith("paired")
                 ? "Each participant contributes one observation in each condition."
                 : "Per-group n is half the total (equal groups)."}
            </p>
          </>
        )}

          </>
        )}
      </section>
    </Surface>
  );
}

function PowerChart({ doc }: { doc: PowerDoc }) {
  const plotW = SVG_W - M.left - M.right;
  const paired = doc.model.startsWith("paired");
  const xMax = doc.maxTotalN;
  const x = (totalN: number) => M.left + (plotW * totalN) / xMax;
  const y = (power: number) => M.top + PLOT_H * (1 - power);

  const xTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => ({
    label: String(Math.round(xMax * f)),
    x: M.left + plotW * f,
  }));
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => ({
    label: String(f * 100),
    y: M.top + PLOT_H * (1 - f),
  }));
  const totalH = M.top + M.bottom + PLOT_H;

  return (
    <div className="rounded-card border border-border bg-surface p-2">
      <svg
        viewBox={`0 0 ${SVG_W} ${totalH}`}
        className="h-auto w-full"
        role="img"
        aria-label={`Power curve: power vs total n for effect sizes ${doc.curves
          .map((c) => c.effectSize)
          .join(", ")}`}
        data-agent="power-curve"
      >
        {/* Reference line at the target power */}
        <line
          x1={M.left}
          y1={y(doc.powerTarget)}
          x2={SVG_W - M.right}
          y2={y(doc.powerTarget)}
          stroke="var(--viz-axis)"
          strokeWidth={1}
          strokeDasharray="4,3"
        />
        <text
          x={SVG_W - M.right - 4}
          y={y(doc.powerTarget) - 6}
          textAnchor="end"
          className="fill-text-muted type-caption"
        >
          {doc.powerTarget * 100}% target
        </text>

        {/* Grid */}
        {yTicks.map((t) => (
          <g key={`y-${t.label}`}>
            <line
              x1={M.left}
              y1={t.y}
              x2={SVG_W - M.right}
              y2={t.y}
              stroke="var(--viz-grid)"
              strokeWidth={0.5}
              strokeDasharray="2,2"
            />
            <text
              x={M.left - 6}
              y={t.y + 3}
              textAnchor="end"
              className="tabular fill-text-muted type-caption"
            >
              {t.label}
            </text>
          </g>
        ))}
        {xTicks.map((t) => (
          <g key={`x-${t.label}`}>
            <line
              x1={t.x}
              y1={M.top}
              x2={t.x}
              y2={M.top + PLOT_H}
              stroke="var(--viz-grid)"
              strokeWidth={0.5}
              strokeDasharray="2,2"
            />
            <text
              x={t.x}
              y={M.top + PLOT_H + 16}
              textAnchor="middle"
              className="tabular fill-text-muted type-caption"
            >
              {t.label}
            </text>
          </g>
        ))}

        {/* Axes */}
        <line
          x1={M.left}
          y1={M.top + PLOT_H}
          x2={SVG_W - M.right}
          y2={M.top + PLOT_H}
          stroke="var(--viz-axis)"
          strokeWidth={1}
        />
        <line
          x1={M.left}
          y1={M.top}
          x2={M.left}
          y2={M.top + PLOT_H}
          stroke="var(--viz-axis)"
          strokeWidth={1}
        />
        <text
          x={M.left + plotW / 2}
          y={totalH - 4}
          textAnchor="middle"
          className="fill-text-muted type-caption"
        >
          {paired ? "participants with both conditions" : "total n (both groups)"}
        </text>
        <text
          x={12}
          y={M.top + PLOT_H / 2}
          textAnchor="middle"
          className="fill-text-muted type-caption"
          transform={`rotate(-90 12 ${M.top + PLOT_H / 2})`}
        >
          power (%)
        </text>

        {/* One line per effect size; a filled diamond marks the first n at
            which the target is reached. */}
        {doc.curves.map((curve, i) => {
          const { color, dash } = seriesOf(curve.effectSize);
          const points = curve.points
            .map((p) => `${x(p.totalN).toFixed(1)},${y(p.power).toFixed(1)}`)
            .join(" ");
          const req = doc.requiredN[i];
          return (
            <g key={curve.effectSize}>
              <polyline
                points={points}
                fill="none"
                stroke={color}
                strokeWidth={1.6}
                strokeDasharray={dash || undefined}
              />
              {req?.reachesTarget && req.nPerGroup !== null && (
                <circle
                  cx={x(paired ? req.totalN ?? 0 : 2 * req.nPerGroup)}
                  cy={y(req.powerAtTargetN ?? 0)}
                  r={4}
                  fill="var(--surface)"
                  stroke={color}
                  strokeWidth={1.5}
                >
                  <title>{`d=${curve.effectSize}: ${req.totalN} total reaches ${doc.powerTarget * 100}% power`}</title>
                </circle>
              )}
            </g>
          );
        })}

        {/* Legend  -  the same stroke the curve is drawn with, dash included, so
            the key is readable as a key without reference to colour. */}
        <g transform={`translate(${M.left}, ${M.top - 6})`}>
          {doc.curves.map((curve, i) => (
            <g key={curve.effectSize} transform={`translate(${i * 110}, 0)`}>
              <line
                x1={0}
                y1={0}
                x2={16}
                y2={0}
                stroke={seriesOf(curve.effectSize).color}
                strokeWidth={1.6}
                strokeDasharray={seriesOf(curve.effectSize).dash || undefined}
              />
              <text x={22} y={3} className="fill-text type-caption">
                d={curve.effectSize}
              </text>
            </g>
          ))}
        </g>
      </svg>
    </div>
  );
}

function RequiredTable({
  requirements,
  maxTotalN,
  paired,
}: {
  requirements: PowerRequirement[];
  maxTotalN: number;
  paired: boolean;
}) {
  return (
    <div className="overflow-x-auto rounded-card border border-border bg-surface">
      <table className="w-full border-collapse type-body" data-agent="power-required">
        <thead>
          <tr className="border-b border-border text-left type-caption text-text-muted">
            <th className="px-4 py-2 font-normal">effect size</th>
            <th className="px-4 py-2 font-normal">{paired ? "participants" : "per-group n"}</th>
            <th className="px-4 py-2 font-normal">total n</th>
            <th className="px-4 py-2 font-normal">target reached</th>
          </tr>
        </thead>
        <tbody>
          {requirements.map((r) => (
            <tr key={r.effectSize} className="border-b border-border last:border-0">
              <td className="px-4 py-2 tabular text-text">d = {r.effectSize}</td>
              <td className="px-4 py-2 tabular text-text">
                {r.nPerGroup ?? " - "}
              </td>
              <td className="px-4 py-2 tabular text-text">
                {r.totalN ?? " - "}
              </td>
              <td className="px-4 py-2">
                {r.reachesTarget ? (
                  <span className="flex items-center gap-1 text-text">
                    <Crosshair className="size-3" aria-hidden />
                    {r.totalN} {paired ? "participants" : "total"}
                  </span>
                ) : (
                  <span className="text-text-muted">
                    not within {maxTotalN} explored
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
