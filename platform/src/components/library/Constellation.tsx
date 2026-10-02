import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Maximize2 } from "lucide-react";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { layoutGraph, degreeMap, type PositionedNode } from "@/lib/forceLayout";
import {
  nodeRadius,
  buildAdjacency,
  activeNeighbourhood,
  nodeOpacity,
  edgeState,
  edgeOpacity,
  labelVisible,
  labelMode,
  LENSES,
  lensEdges,
  lensNodes,
  lensCounts,
  curateGraph,
  type Lens,
} from "@/lib/constellationView";
import type { PaperGraph } from "@/lib/studyApi";
import { cn } from "@/lib/cn";

const W = 1000;
const H = 620;
const MIN_K = 0.4;
const MAX_K = 4;
const DRAG_THRESHOLD = 4;

const EDGE: Record<string, { color: string; label: string }> = {
  references: { color: "var(--series-1)", label: "references" },
  citations: { color: "var(--series-5)", label: "citations" },
  recommendations: { color: "var(--series-3)", label: "recommended" },
};

function edgePath(
  a: PositionedNode,
  b: PositionedNode,
  kind: string,
  index: number,
): string {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const direction = dx >= 0 ? 1 : -1;
  const bend = kind === "recommendations" ? 34 : 22 + (index % 3) * 8;
  const cx = (a.x + b.x) / 2;
  const cy = (a.y + b.y) / 2 + direction * bend + (dy === 0 ? 8 : 0);
  return `M ${a.x} ${a.y} Q ${cx} ${cy} ${b.x} ${b.y}`;
}

const TITLE_LABEL_MAX = 34;

function truncatedTitle(title: string): string {
  return title.length > TITLE_LABEL_MAX
    ? `${title.slice(0, TITLE_LABEL_MAX - 1)}…`
    : title;
}

function nodeLabel(n: PositionedNode): string {
  const author = n.authors?.[0]?.split(" ").pop();
  const who = author ? (n.authors!.length > 1 ? `${author} et al.` : author) : "";
  if (who && n.year) return `${who}, ${n.year}`;
  if (who) return who;
  return n.title ? truncatedTitle(n.title) : "";
}

type View = { x: number; y: number; k: number };
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

function fitView(nodes: PositionedNode[]): View {
  if (nodes.length === 0) return { x: 0, y: 0, k: 1 };
  const xs = nodes.map((n) => n.x);
  const ys = nodes.map((n) => n.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const padding = 56;
  const spanX = Math.max(maxX - minX, 120);
  const spanY = Math.max(maxY - minY, 96);
  const k = clamp(
    Math.min((W - padding * 2) / spanX, (H - padding * 2) / spanY),
    MIN_K,
    MAX_K,
  );
  return {
    x: W / 2 - ((minX + maxX) / 2) * k,
    y: H / 2 - ((minY + maxY) / 2) * k,
    k,
  };
}

export function Constellation({
  graph,
  selected,
  onSelect,
}: {
  graph: PaperGraph;
  selected: string | null;
  onSelect: (ref: string) => void;
}) {

  const [lens, setLens] = useState<Lens>("all");
  const curatedGraph = useMemo(() => curateGraph(graph), [graph]);
  const visibleCounts = useMemo(
    () =>
      Object.fromEntries(
        LENSES.map((entry) => [
          entry.id,
          lensCounts(curatedGraph.nodes, curatedGraph.edges)[entry.id],
        ]),
      ) as Record<Lens, number>,
    [curatedGraph],
  );
  const edges = useMemo(
    () => lensEdges(curatedGraph.edges, lens),
    [curatedGraph, lens],
  );
  const nodes = useMemo(
    () => lensNodes(curatedGraph.nodes, curatedGraph.edges, lens),
    [curatedGraph, lens],
  );

  const base = useMemo(
    () =>
      layoutGraph(nodes, edges, {
        width: W,
        height: H,
        spread: true,
      }),
    [nodes, edges],
  );
  const degrees = useMemo(() => degreeMap(nodes, edges), [nodes, edges]);
  const adjacency = useMemo(() => buildAdjacency(edges), [edges]);

  const [moved, setMoved] = useState<Record<string, { x: number; y: number }>>({});

  const settled = base;

  useEffect(() => {
    setView(fitView(base));
    setMoved({});
  }, [base]);

  const positioned = useMemo(
    () => settled.map((n) => ({ ...n, ...(moved[n.paperRef] ?? {}) })),
    [settled, moved],
  );

  const posByRef = useMemo(
    () => new Map(positioned.map((n) => [n.paperRef, n])),
    [positioned],
  );
  const maxCitationCount = useMemo(
    () => Math.max(...nodes.map((n) => n.citationCount ?? 0), 0),
    [nodes],
  );
  const svgRef = useRef<SVGSVGElement>(null);
  const [view, setView] = useState<View>({ x: 0, y: 0, k: 1 });

  const [focusRef, setFocusRef] = useState<string | null>(null);
  const active = useMemo(() => activeNeighbourhood(focusRef, adjacency), [focusRef, adjacency]);

  const gesture = useRef<{
    kind: "pan" | "node";
    ref?: string;
    startSx: number;
    startSy: number;
    startView: View;
    moved: boolean;
  } | null>(null);

  const toBox = useCallback((clientX: number, clientY: number) => {
    const rect = svgRef.current!.getBoundingClientRect();
    const scale = Math.min(rect.width / W, rect.height / H);
    const offsetX = (rect.width - W * scale) / 2;
    const offsetY = (rect.height - H * scale) / 2;
    return {
      sx: (clientX - rect.left - offsetX) / scale,
      sy: (clientY - rect.top - offsetY) / scale,
    };
  }, []);

  const beginPan = (e: React.PointerEvent<SVGSVGElement>) => {

    const { sx, sy } = toBox(e.clientX, e.clientY);
    gesture.current = { kind: "pan", startSx: sx, startSy: sy, startView: view, moved: false };
    svgRef.current?.setPointerCapture(e.pointerId);
  };

  const beginNode = (e: React.PointerEvent, ref: string) => {

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

      const nx = (sx - view.x) / view.k;
      const ny = (sy - view.y) / view.k;
      setMoved((m) => ({ ...m, [g.ref!]: { x: nx, y: ny } }));
    }
  };

  const onUp = (e: React.PointerEvent) => {
    const g = gesture.current;
    gesture.current = null;
    if (!g) return;

    if (!g.moved && g.kind === "node" && g.ref) onSelect(g.ref);
    if (svgRef.current?.hasPointerCapture(e.pointerId))
      svgRef.current.releasePointerCapture(e.pointerId);
  };

  const zoomAt = useCallback(
    (sx: number, sy: number, deltaY: number) => {
      setView((v) => {
        const k = clamp(v.k * Math.exp(-deltaY * 0.0015), MIN_K, MAX_K);

        const lx = (sx - v.x) / v.k;
        const ly = (sy - v.y) / v.k;
        return { k, x: sx - lx * k, y: sy - ly * k };
      });
    },
    [],
  );

  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const handler = (e: WheelEvent) => {
      e.preventDefault();
      const { sx, sy } = toBox(e.clientX, e.clientY);
      zoomAt(sx, sy, e.deltaY);
    };
    el.addEventListener("wheel", handler, { passive: false });
    return () => el.removeEventListener("wheel", handler);
  }, [toBox, zoomAt]);

  const fit = () => {
    setView(fitView(base));
    setMoved({});
  };

  if (graph.nodes.length === 0) {
    return (
      <p className="p-6 type-body text-text-muted">
        No papers yet. Add an arXiv id, DOI, or PDF, and the neighbourhood grows
        from the citation service.
      </p>
    );
  }

  const panning = gesture.current?.kind === "pan";

  const alwaysLabels = labelMode(nodes.length) === "always";
  const sparse = nodes.length <= 5;

  return (
    <figure className="m-0 flex flex-col gap-2">

      <div
        className="flex flex-wrap items-center gap-2"
      >
        <SegmentedControl
          value={lens}
          onChange={setLens}
          aria-label="Which citation relation to show"
          options={LENSES.map((l) => ({
            value: l.id,
            label:
              visibleCounts[l.id] > 0
                ? `${l.label} (${visibleCounts[l.id]})`
                : l.label,
            hint: l.hint,
          }))}
        />
      </div>

      <div
        className={cn(
          "relative w-full overflow-hidden rounded-card bg-bg",
          sparse ? "h-[var(--constellation-h-sparse)]" : "h-[var(--constellation-h)]",
        )}
      >

        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(120% 100% at 50% 50%, transparent 55%, color-mix(in srgb, var(--ink) 6%, transparent) 100%)",
          }}
        />
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="xMidYMid meet"
          className={cn(
            "h-full w-full touch-none select-none",
            panning ? "cursor-grabbing" : "cursor-grab",
          )}
          role="group"
          aria-label="Citation constellation of the study's papers. Drag to pan, scroll to zoom."
          onPointerDown={beginPan}
          onPointerMove={onMove}
          onPointerUp={onUp}
          onPointerCancel={onUp}
          onKeyDown={(e) => {
            if (e.key === "Escape") setFocusRef(null);
          }}
        >
          <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
            {edges.map((e, edgeIndex) => {
              const a = posByRef.get(e.src);
              const b = posByRef.get(e.dst);
              if (!a || !b) return null;
              const state = edgeState(e.src, e.dst, focusRef);
              const edge = EDGE[e.kind] ?? { color: "var(--viz-axis)", label: "relation" };
              return (
                <path
                  key={`${e.src}-${e.dst}-${e.kind}`}
                  d={edgePath(a, b, e.kind, edgeIndex)}
                  fill="none"
                  stroke={edge.color}
                  strokeWidth={state === "incident" ? 2.2 : 1.5}
                  strokeDasharray={e.kind === "recommendations" ? "4 5" : undefined}
                  vectorEffect="non-scaling-stroke"
                  opacity={edgeOpacity(state)}
                  className="transition-opacity duration-standard"
                />
              );
            })}
            {[...positioned.filter((n) => !n.ingested), ...positioned.filter((n) => n.ingested)].map((n) => {
              const isSel = n.paperRef === selected;
              const inFocusNeighbourhood = active.has(n.paperRef);
              const r = nodeRadius(
                degrees.get(n.paperRef) ?? 0,
                n.citationCount,
                maxCitationCount,
              );

              const hasAuthor = Boolean(n.authors?.[0]);
              const hasTitle = Boolean(n.title);
              const hasIdentity = alwaysLabels ? hasAuthor || hasTitle : hasAuthor;
              const showLabel =
                (n.ingested || isSel || inFocusNeighbourhood) &&
                (hasIdentity || isSel || inFocusNeighbourhood) &&
                (alwaysLabels ||
                  labelVisible({
                    selected: isSel,
                    inFocusNeighbourhood,
                    radius: r,
                    zoomK: view.k,
                  }));
              const label = showLabel ? nodeLabel(n) : "";
              const labelAnchor = n.x < W * 0.24 ? "start" : n.x > W * 0.76 ? "end" : "middle";
              const labelOffset = labelAnchor === "start" ? r + 8 : labelAnchor === "end" ? -(r + 8) : 0;
              const highlighted = isSel || inFocusNeighbourhood;
              return (
                <g
                  key={n.paperRef}
                  transform={`translate(${n.x},${n.y})`}
                  className="cursor-pointer"
                  role="button"
                  tabIndex={0}
                  opacity={nodeOpacity(n.paperRef, active)}
                  style={{ transition: "opacity var(--motion-standard)" }}
                  aria-label={
                    (n.title || n.paperRef) + (n.ingested ? "" : " (suggested, click to add)")
                  }
                  onPointerDown={(ev) => beginNode(ev, n.paperRef)}
                  onPointerEnter={() => setFocusRef(n.paperRef)}
                  onPointerLeave={() => setFocusRef((cur) => (cur === n.paperRef ? null : cur))}
                  onFocus={() => setFocusRef(n.paperRef)}
                  onBlur={() => setFocusRef((cur) => (cur === n.paperRef ? null : cur))}
                  onKeyDown={(ev) => ev.key === "Enter" && onSelect(n.paperRef)}
                >
                  <circle
                    r={r}
                    fill={n.ingested ? "var(--accent)" : "var(--series-3)"}
                    fillOpacity={n.ingested ? 0.96 : 0.9}
                    stroke={
                      highlighted
                        ? "var(--series-4)"
                        : n.ingested
                          ? "var(--accent)"
                          : "var(--series-3)"
                    }
                    strokeWidth={highlighted ? 3 : 1.5}
                    vectorEffect="non-scaling-stroke"
                  />
                  {label && (
                    <text
                      x={labelOffset}
                      y={r + 11}
                      textAnchor={labelAnchor}
                      transform={`scale(${1 / view.k})`}

                      className="fill-text-muted text-legend-svg"
                      stroke="var(--bg)"
                      strokeWidth={3}
                      style={{ paintOrder: "stroke" }}
                    >
                      {label}
                    </text>
                  )}
                  <title>
                    {n.title || n.paperRef}
                    {n.citationCount != null ? ` · ${n.citationCount} citations` : ""}
                    {n.ingested ? "" : " · suggested, click to add to the study"}
                  </title>
                </g>
              );
            })}
          </g>
        </svg>
        <button
          type="button"
          onClick={fit}
          className="absolute right-2 top-2 flex items-center gap-1 rounded-input border border-border-strong bg-surface px-2 py-1 type-caption font-medium text-text shadow-mark transition-colors duration-fast hover:bg-zone-9 hover:text-text"
          aria-label="Reset the view"
        >
          <Maximize2 className="size-3.5" aria-hidden /> Fit
        </button>
      </div>

      <figcaption className="flex flex-col gap-3 type-caption text-text-muted">
        <span className="text-text-muted">Drag to pan · scroll to zoom · select a paper to inspect it</span>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <LegendDot filled label="ingested" />
          <LegendDot color="var(--series-3)" label="suggested, click to add" />
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
        </div>
      </figcaption>
    </figure>
  );
}

function LegendDot({
  filled = true,
  color,
  label,
}: {
  filled?: boolean;
  color?: string;
  label: string;
}) {
  return (
    <span className="flex items-center gap-1">
      <span
        aria-hidden
        className={cn(
          "inline-block size-2.5 rounded-chip",
          !color && filled && "bg-accent",
          !color && !filled && "border border-viz-axis",
        )}
        style={color ? { background: color } : undefined}
      />
      {label}
    </span>
  );
}
