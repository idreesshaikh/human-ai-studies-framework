import { useEffect, useMemo, useState } from "react";
import { Table2, ChartScatter } from "lucide-react";
import { Button } from "@/components/ui/button";
import { studyApi } from "@/lib/studyApi";
import {
  assembleLanes,
  timeScale,
  parseTs,
  type EventRow,
  type Lane,
} from "@/lib/timeline";

/* Per-session swimlane timeline (FR-DASH-4): one lane per leg, events as marks
 * positioned by ts on a shared time axis. Pure rendering — no new backend
 * contract, no new privacy surface: every row is already join-keyed by wall #4.
 * Table-view twin ships from day one (wall #10, NFR-12). */

const SVG_W = 800;
const M = { left: 60, right: 20, top: 12, bottom: 32 };
const LANE_H = 28;
const LANE_GAP = 8;
const MARK_R = 4;
const FLAG_MARK_R = 6;

const LANE_COLORS = [
  "var(--series-1)",
  "var(--series-3)",
  "var(--series-5)",
  "var(--series-7)",
  "var(--series-2)",
  "var(--series-4)",
];

interface EventDisplayData {
  x: number;
  row: EventRow;
  laneIndex: number;
}

export function SwimlaneTimeline({
  sessionId,
  studyId,
  onClose,
}: {
  sessionId: string;
  studyId: string;
  onClose?: () => void;
}) {
  const [events, setEvents] = useState<EventRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [asTable, setAsTable] = useState(false);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(null);
    studyApi
      .sessionEvents(studyId, sessionId)
      .then((data) => {
        if (!live) return;
        setEvents(data);
        setLoading(false);
      })
      .catch((err: Error) => {
        if (!live) return;
        setError(err.message);
        setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [sessionId, studyId]);

  const lanes = useMemo(() => assembleLanes(events), [events]);
  const scale = useMemo(() => timeScale(events, SVG_W, M.left, M.right), [events]);

  const displayData = useMemo(() => {
    const data: EventDisplayData[] = [];
    for (let li = 0; li < lanes.length; li++) {
      for (const ev of lanes[li].events) {
        data.push({
          x: scale(ev.ts),
          row: ev,
          laneIndex: li,
        });
      }
    }
    return data;
  }, [lanes, scale]);

  const totalH = M.top + M.bottom + lanes.length * (LANE_H + LANE_GAP);

  // Collect flags across all events
  const allFlagKinds = useMemo(() => {
    const kinds = new Set<string>();
    for (const ev of events) {
      for (const f of ev.flags) kinds.add(f);
    }
    return [...kinds].sort();
  }, [events]);

  if (loading) {
    return (
      <div className="rounded-card border border-border bg-surface p-4 text-sm text-text-muted">
        Loading events for {sessionId}…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-card border border-border bg-surface p-4">
        <p className="text-sm text-unsourced">Failed to load timeline: {error}</p>
      </div>
    );
  }

  if (lanes.length === 0) {
    return (
      <div className="rounded-card border border-border bg-surface p-4">
        <p className="text-sm text-text-muted">
          No events for session {sessionId}.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-text">
          Timeline — {sessionId}
          <span className="ml-2 text-xs text-text-muted">
            {events.length} events · {lanes.length} lanes
            {allFlagKinds.length > 0 && ` · ${allFlagKinds.join(", ")}`}
          </span>
        </h3>
        <div className="flex items-center gap-2">
          {onClose && (
            <Button size="sm" variant="ghost" className="text-xs" onClick={onClose}>
              Close
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            className="text-xs"
            onClick={() => setAsTable((v) => !v)}
          >
            {asTable ? <ChartScatter aria-hidden /> : <Table2 aria-hidden />}
            {asTable ? "Chart" : "Table"}
          </Button>
        </div>
      </div>

      {asTable ? (
        <TableTimeline lanes={lanes} allFlagKinds={allFlagKinds} />
      ) : (
        <ChartTimeline
          lanes={lanes}
          displayData={displayData}
          totalH={totalH}
        />
      )}
    </div>
  );
}

function ChartTimeline({
  lanes,
  displayData,
  totalH,
}: {
  lanes: Lane[];
  displayData: EventDisplayData[];
  totalH: number;
}) {
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);
  const plotW = SVG_W - M.left - M.right;

  // Compute time axis ticks
  const allTs = displayData.map((d) => parseTs(d.row.ts));
  const minTs = allTs.length ? Math.min(...allTs) : 0;
  const maxTs = allTs.length ? Math.max(...allTs) : 1;
  const range = maxTs - minTs;
  const tickCount = 5;
  const ticks: { label: string; x: number }[] = [];
  if (range > 0) {
    for (let i = 0; i <= tickCount; i++) {
      const t = minTs + (range * i) / tickCount;
      const d = new Date(t);
      const label = `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}:${d.getSeconds().toString().padStart(2, "0")}`;
      const x = M.left + (plotW * i) / tickCount;
      ticks.push({ label, x });
    }
  }

  return (
    <div className="relative overflow-x-auto rounded-card border border-border bg-surface p-2">
      <svg
        viewBox={`0 0 ${SVG_W} ${totalH}`}
        className="h-auto w-full"
        role="img"
        aria-label={`Session timeline: ${lanes.length} lanes, ${displayData.length} events`}
        data-agent="swimlane-timeline"
      >
        {/* Time axis */}
        <line
          x1={M.left}
          y1={totalH - M.bottom}
          x2={SVG_W - M.right}
          y2={totalH - M.bottom}
          stroke="var(--viz-axis)"
          strokeWidth={1}
        />
        {ticks.map((t, i) => (
          <g key={i}>
            <line
              x1={t.x}
              y1={M.top}
              x2={t.x}
              y2={totalH - M.bottom}
              stroke="var(--viz-grid)"
              strokeWidth={0.5}
              strokeDasharray={i === 0 || i === ticks.length - 1 ? "" : "2,2"}
            />
            <text
              x={t.x}
              y={totalH - M.bottom + 16}
              textAnchor="middle"
              className="tabular fill-text-muted text-xs"
            >
              {t.label}
            </text>
          </g>
        ))}

        {/* Lanes */}
        {lanes.map((lane, li) => {
          const y = M.top + li * (LANE_H + LANE_GAP);
          const color = LANE_COLORS[li % LANE_COLORS.length];

          return (
            <g key={lane.source}>
              {/* Lane label */}
              <text
                x={M.left - 8}
                y={y + LANE_H / 2}
                textAnchor="end"
                dominantBaseline="middle"
                className="fill-text text-xs font-medium"
              >
                {lane.label}
              </text>

              {/* Lane background */}
              <rect
                x={M.left}
                y={y}
                width={plotW}
                height={LANE_H}
                fill={color}
                opacity={0.04}
                rx={3}
              />
              {/* Lane bottom line */}
              <line
                x1={M.left}
                y1={y + LANE_H}
                x2={M.left + plotW}
                y2={y + LANE_H}
                stroke={color}
                strokeWidth={1}
                opacity={0.2}
              />

              {/* Events */}
              {displayData
                .filter((d) => d.laneIndex === li)
                .map((d, pi) => {
                  const hasFlags = d.row.flags.length > 0;
                  return (
                    <circle
                      key={`${d.row.seq}-${pi}`}
                      cx={d.x}
                      cy={y + LANE_H / 2}
                      r={hasFlags ? FLAG_MARK_R : MARK_R}
                      fill={hasFlags ? "var(--unsourced)" : color}
                      stroke={hasFlags ? "var(--surface)" : "none"}
                      strokeWidth={hasFlags ? 1.5 : 0}
                      opacity={hasFlags ? 0.9 : 0.7}
                      style={{ cursor: "pointer" }}
                      onPointerMove={(e) =>
                        setTip({
                          x: e.clientX + 12,
                          y: e.clientY + 12,
                          text: `[${lane.label}] ${d.row.type} @ ${d.row.ts}${hasFlags ? ` · flags: ${d.row.flags.join(", ")}` : ""}`,
                        })
                      }
                      onPointerLeave={() => setTip(null)}
                    />
                  );
                })}
            </g>
          );
        })}
      </svg>

      {tip && (
        <div
          className="pointer-events-none fixed z-50 max-w-sm rounded-input border border-border-strong bg-surface-raised px-2 py-1 text-xs text-text shadow-brutal"
          style={{ left: tip.x, top: tip.y }}
        >
          {tip.text}
        </div>
      )}
    </div>
  );
}

function TableTimeline({
  lanes,
  allFlagKinds,
}: {
  lanes: Lane[];
  allFlagKinds: string[];
}) {
  const flat = useMemo(() => {
    const rows: {
      lane: string;
      source: string;
      type: string;
      ts: string;
      seq: number;
      flags: string[];
    }[] = [];
    for (const lane of lanes) {
      for (const ev of lane.events) {
        rows.push({
          lane: lane.label,
          source: ev.source,
          type: ev.type,
          ts: ev.ts,
          seq: ev.seq,
          flags: ev.flags,
        });
      }
    }
    // Sort by ts, then seq
    rows.sort((a, b) => a.ts.localeCompare(b.ts) || a.seq - b.seq);
    return rows;
  }, [lanes]);

  return (
    <div className="overflow-x-auto rounded-card border border-border bg-surface">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-text-muted">
            <th className="px-3 py-2 font-medium">Lane</th>
            <th className="px-3 py-2 font-medium">Type</th>
            <th className="px-3 py-2 font-medium">Timestamp</th>
            <th className="px-3 py-2 font-medium">Seq</th>
            {allFlagKinds.length > 0 && (
              <th className="px-3 py-2 font-medium">Flags</th>
            )}
          </tr>
        </thead>
        <tbody className="tabular">
          {flat.map((row, i) => (
            <tr
              key={i}
              className={`border-b border-border last:border-0 ${row.flags.length > 0 ? "bg-unsourced/5" : ""}`}
            >
              <td className="px-3 py-1.5 text-text">{row.lane}</td>
              <td className="px-3 py-1.5 text-text-muted">{row.type}</td>
              <td className="px-3 py-1.5 text-text-muted">{row.ts}</td>
              <td className="px-3 py-1.5 text-text-muted">{row.seq}</td>
              {allFlagKinds.length > 0 && (
                <td className="px-3 py-1.5 text-unsourced">
                  {row.flags.length > 0 ? row.flags.join(", ") : ""}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
