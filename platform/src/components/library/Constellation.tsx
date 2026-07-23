import { useCallback, useMemo, useRef, useState } from "react";
import { Maximize2 } from "lucide-react";
import { layoutGraph, type PositionedNode } from "@/lib/forceLayout";
import type { PaperGraph } from "@/lib/studyApi";
import { cn } from "@/lib/cn";

/* The citation constellation (FR-LIT-2) — a study's papers grow a graph around
 * themselves: seed → neighbourhood → grow, ResearchRabbit-style on open data.
 * Deterministic force layout (no d3-force, D17), the dataviz series palette for
 * edge kinds, node radius by citation count. Ingested papers anchor the centre;
 * suggestions drift to the rim, one click from joining the study.
 *
 * Interaction (hand-rolled on the SVG transform, still no d3): drag the
 * background to pan, scroll to zoom toward the cursor, drag a node to nudge it,
 * and "Fit" resets the view. The pane is a fixed height so the graph no longer
 * grows past the column or collapses to a sliver. */

const W = 640;
const H = 440;
const MIN_K = 0.4;
const MAX_K = 4;
const DRAG_THRESHOLD = 4; // px of movement before a press counts as a drag

// Edge kinds → non-adjacent, CVD-distinct series slots (the legend labels carry
// identity too — never color alone).
const EDGE: Record<string, { color: string; label: string }> = {
  references: { color: "var(--series-1)", label: "references" },
  citations: { color: "var(--series-5)", label: "citations" },
  recommendations: { color: "var(--series-3)", label: "recommended" },
};

function radius(n: PositionedNode): number {
  const base = n.ingested ? 9 : 5;
  return base + Math.min(6, Math.log10((n.citationCount ?? 0) + 1) * 2);
}

/** "Surname et al., 2019" — the short label a node shows without a hover. */
function nodeLabel(n: PositionedNode): string {
  const author = n.authors?.[0]?.split(" ").pop();
  const who = author ? (n.authors!.length > 1 ? `${author} et al.` : author) : "";
  if (who && n.year) return `${who}, ${n.year}`;
  return who || (n.year ? String(n.year) : "");
}

type View = { x: number; y: number; k: number };
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

export function Constellation({
  graph,
  selected,
  onSelect,
}: {
  graph: PaperGraph;
  selected: string | null;
  onSelect: (ref: string) => void;
}) {
  const base = useMemo(
    () => layoutGraph(graph.nodes, graph.edges, { width: W, height: H }),
    [graph],
  );
  // Per-node position overrides produced by dragging a node.
  const [moved, setMoved] = useState<Record<string, { x: number; y: number }>>({});
  const positioned = useMemo(
    () => base.map((n) => (moved[n.paperRef] ? { ...n, ...moved[n.paperRef] } : n)),
    [base, moved],
  );
  const posByRef = useMemo(
    () => new Map(positioned.map((n) => [n.paperRef, n])),
    [positioned],
  );

  const svgRef = useRef<SVGSVGElement>(null);
  const [view, setView] = useState<View>({ x: 0, y: 0, k: 1 });
  // Live gesture state kept in a ref so pointer handlers don't re-subscribe.
  const gesture = useRef<{
    kind: "pan" | "node";
    ref?: string;
    startSx: number;
    startSy: number;
    startView: View;
    moved: boolean;
  } | null>(null);

  // Client px → viewBox units (the SVG is drawn in a 0..W / 0..H box that CSS
  // then scales to fit the pane).
  const toBox = useCallback((clientX: number, clientY: number) => {
    const rect = svgRef.current!.getBoundingClientRect();
    return {
      sx: ((clientX - rect.left) / rect.width) * W,
      sy: ((clientY - rect.top) / rect.height) * H,
    };
  }, []);

  const beginPan = (e: React.PointerEvent<SVGSVGElement>) => {
    // Only the background starts a pan; node handlers stop propagation.
    const { sx, sy } = toBox(e.clientX, e.clientY);
    gesture.current = { kind: "pan", startSx: sx, startSy: sy, startView: view, moved: false };
    svgRef.current?.setPointerCapture(e.pointerId);
  };

  const beginNode = (e: React.PointerEvent, ref: string) => {
    // Don't let this also start a background pan; capture on the SVG so its
    // move/up handlers keep firing for the rest of the drag.
    e.stopPropagation();
    const { sx, sy } = toBox(e.clientX, e.clientY);
    gesture.current = { kind: "node", ref, startSx: sx, startSy: sy, startView: view, moved: false };
    svgRef.current?.setPointerCapture(e.pointerId);
  };

  const onMove = (e: React.PointerEvent) => {
    const g = gesture.current;
    if (!g) return;
    const { sx, sy } = toBox(e.clientX, e.clientY);
    const dx = sx - g.startSx;
    const dy = sy - g.startSy;
    if (!g.moved && Math.hypot(dx, dy) > DRAG_THRESHOLD) g.moved = true;
    if (!g.moved) return;
    if (g.kind === "pan") {
      setView({ ...g.startView, x: g.startView.x + dx, y: g.startView.y + dy });
    } else if (g.ref) {
      // Node coords live in the pre-transform space, so undo the current view.
      const nx = (sx - view.x) / view.k;
      const ny = (sy - view.y) / view.k;
      setMoved((m) => ({ ...m, [g.ref!]: { x: nx, y: ny } }));
    }
  };

  const onUp = (e: React.PointerEvent) => {
    const g = gesture.current;
    gesture.current = null;
    if (!g) return;
    // A press that never crossed the threshold is a click → selection.
    if (!g.moved && g.kind === "node" && g.ref) onSelect(g.ref);
    if (svgRef.current?.hasPointerCapture(e.pointerId))
      svgRef.current.releasePointerCapture(e.pointerId);
  };

  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const { sx, sy } = toBox(e.clientX, e.clientY);
    const k = clamp(view.k * Math.exp(-e.deltaY * 0.0015), MIN_K, MAX_K);
    // Keep the point under the cursor fixed while zooming.
    const lx = (sx - view.x) / view.k;
    const ly = (sy - view.y) / view.k;
    setView({ k, x: sx - lx * k, y: sy - ly * k });
  };

  const fit = () => {
    setView({ x: 0, y: 0, k: 1 });
    setMoved({});
  };

  if (graph.nodes.length === 0) {
    return (
      <p className="p-6 text-sm text-text-muted">
        No papers yet. Add an arXiv id, DOI, or PDF — the neighbourhood grows
        from the citation service.
      </p>
    );
  }

  const panning = gesture.current?.kind === "pan";

  return (
    <figure className="m-0 flex flex-col gap-2">
      <div className="relative h-[22.5rem] w-full overflow-hidden rounded-card bg-bg">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="xMidYMid meet"
          className={cn(
            "h-full w-full touch-none select-none",
            panning ? "cursor-grabbing" : "cursor-grab",
          )}
          role="img"
          aria-label="Citation constellation of the study's papers. Drag to pan, scroll to zoom."
          data-agent="constellation"
          onPointerDown={beginPan}
          onPointerMove={onMove}
          onPointerUp={onUp}
          onPointerCancel={onUp}
          onWheel={onWheel}
        >
          <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
            {graph.edges.map((e) => {
              const a = posByRef.get(e.src);
              const b = posByRef.get(e.dst);
              if (!a || !b) return null;
              return (
                <line
                  key={`${e.src}-${e.dst}-${e.kind}`}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={EDGE[e.kind]?.color ?? "var(--viz-axis)"}
                  strokeWidth={1}
                  opacity={0.4}
                />
              );
            })}
            {positioned.map((n) => {
              const isSel = n.paperRef === selected;
              // A harvested neighbourhood runs to hundreds of suggested stubs
              // (FR-LIT-2 fetches up to 250 per paper) - a permanent label on
              // every one is illegible clutter. Label the few that matter:
              // ingested papers and whichever one is selected.
              const label = n.ingested || isSel ? nodeLabel(n) : "";
              const r = radius(n);
              return (
                <g
                  key={n.paperRef}
                  transform={`translate(${n.x},${n.y})`}
                  className="cursor-pointer"
                  role="button"
                  tabIndex={0}
                  aria-label={
                    (n.title || n.paperRef) + (n.ingested ? "" : " — suggested, click to add")
                  }
                  onPointerDown={(ev) => beginNode(ev, n.paperRef)}
                  onKeyDown={(ev) => ev.key === "Enter" && onSelect(n.paperRef)}
                >
                  <circle
                    r={r}
                    fill={n.ingested ? "var(--accent)" : "var(--surface)"}
                    stroke={isSel ? "var(--accent)" : "var(--viz-axis)"}
                    strokeWidth={isSel ? 3 : n.ingested ? 0 : 1.5}
                    strokeDasharray={n.ingested ? undefined : "2 2"}
                  />
                  {label && (
                    <text
                      y={r + 11}
                      textAnchor="middle"
                      className="fill-text-muted text-[0.625rem]"
                    >
                      {label}
                    </text>
                  )}
                  <title>
                    {n.title || n.paperRef}
                    {n.citationCount != null ? ` · ${n.citationCount} citations` : ""}
                    {n.ingested ? "" : " · suggested — click to add to the study"}
                  </title>
                </g>
              );
            })}
          </g>
        </svg>
        <button
          type="button"
          onClick={fit}
          className="absolute right-2 top-2 flex items-center gap-1 rounded-input border border-border-strong bg-surface px-2 py-1 text-xs font-medium text-text shadow-brutal-sm transition-colors duration-fast hover:bg-accent-soft hover:text-accent"
          aria-label="Reset the view"
        >
          <Maximize2 className="size-3.5" aria-hidden /> Fit
        </button>
      </div>

      <figcaption className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-muted">
        <span className="text-text-muted/80">Drag to pan · scroll to zoom · drag a node to move</span>
        <LegendDot filled label="ingested" />
        <LegendDot filled={false} label="suggested — click to add" />
        {Object.entries(EDGE).map(([kind, { color, label }]) => (
          <span key={kind} className="flex items-center gap-1">
            <span
              aria-hidden
              className="inline-block h-0.5 w-4 rounded-chip"
              style={{ background: color }}
            />
            {label}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}

function LegendDot({ filled, label }: { filled: boolean; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span
        aria-hidden
        className={cn(
          "inline-block size-2.5 rounded-chip",
          filled ? "bg-accent" : "border border-viz-axis",
        )}
      />
      {label}
    </span>
  );
}
