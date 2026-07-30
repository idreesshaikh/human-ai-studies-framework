import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Maximize2 } from "lucide-react";
import { layoutGraph, degreeMap, relaxStep, type PositionedNode } from "@/lib/forceLayout";
import {
  nodeRadius,
  buildAdjacency,
  activeNeighbourhood,
  nodeOpacity,
  edgeState,
  edgeOpacity,
  labelVisible,
  driftOffset,
  nextSettleAlpha,
  shouldSettle,
  SETTLE_ALPHA0,
  SETTLE_MAX_MS,
} from "@/lib/constellationView";
import { usePrefersReducedMotion } from "@/lib/usePrefersReducedMotion";
import type { PaperGraph } from "@/lib/studyApi";
import { cn } from "@/lib/cn";

/* The citation constellation (FR-LIT-2, FR-LIT-10) — a study's papers grow a
 * graph around themselves: seed → neighbourhood → grow, Obsidian-graph-view
 * styled: degree-sized dots, near-invisible edges that light up in the
 * hovered/focused neighbourhood, labels that reveal by zoom/focus/selection
 * rather than sitting on permanently, and a gentle idle drift. Deterministic
 * force layout underneath it all (no d3-force, D17) — see forceLayout.ts and
 * constellationView.ts for the pure logic this is glue over.
 *
 * Three motion layers, deliberately separate:
 *   1. `layoutGraph`'s own deterministic solve — the seed, and the only
 *      thing rendered under reduced motion.
 *   2. A bounded rAF "settle" (`relaxStep`, decaying alpha, <1s, skipped
 *      above 150 nodes) that lets the seed visibly relax into place.
 *   3. A render-only sinusoidal drift, added at paint time only — never
 *      written back to any position state, so it cannot diverge.
 *
 * Interaction (hand-rolled on the SVG transform, still no d3): drag the
 * background to pan, scroll to zoom toward the cursor, drag a node to nudge
 * it (a manually-placed node opts out of settle/drift — it stays where it
 * was put), and "Fit" resets the view. */

const W = 640;
const H = 440;
const MIN_K = 0.4;
const MAX_K = 4;
const DRAG_THRESHOLD = 4; // px of movement before a press counts as a drag

// Edge kinds → non-adjacent, CVD-distinct series slots (the legend labels carry
// identity too — never color alone). Only shown at full identity on the
// incident edges of a focused/hovered node; otherwise every edge recedes to
// one neutral, near-invisible line (constellationView.ts's edgeOpacity).
const EDGE: Record<string, { color: string; label: string }> = {
  references: { color: "var(--series-1)", label: "references" },
  citations: { color: "var(--series-5)", label: "citations" },
  recommendations: { color: "var(--series-3)", label: "recommended" },
};

/** "Surname et al., 2019" — the short label a node shows once revealed. */
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
  const reducedMotion = usePrefersReducedMotion();
  const base = useMemo(
    () => layoutGraph(graph.nodes, graph.edges, { width: W, height: H }),
    [graph],
  );
  const degrees = useMemo(() => degreeMap(graph.nodes, graph.edges), [graph]);
  const adjacency = useMemo(() => buildAdjacency(graph.edges), [graph]);

  // Per-node position overrides produced by dragging a node — the one thing
  // that opts a node out of the settle/drift layers below (respecting a
  // deliberate placement matters more than the ambient motion).
  const [moved, setMoved] = useState<Record<string, { x: number; y: number }>>({});

  // Layer 2 — the bounded settle: starts at `base` each time the graph
  // itself changes, then relaxes for <1s (skipped under reduced motion or
  // above the node-count limit, in which case it's just `base`).
  const [settled, setSettled] = useState<PositionedNode[]>(base);
  useEffect(() => {
    setSettled(base);
    if (reducedMotion || !shouldSettle(base.length)) return;
    let alpha = SETTLE_ALPHA0;
    let cancelled = false;
    let raf = 0;
    const start = performance.now();
    let current = base;
    const tick = (now: number) => {
      if (cancelled || now - start > SETTLE_MAX_MS) return;
      current = relaxStep(current, graph.edges, alpha, { width: W, height: H });
      setSettled(current);
      alpha = nextSettleAlpha(alpha);
      if (alpha > 0.002) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
    };
    // `graph.edges` is used only for the relax math, not as a re-trigger —
    // it's already implied by `base` changing when the graph does.
  }, [base, reducedMotion]);

  // Layer 3 — the render-only idle drift: a ticking clock, nothing more.
  // Never influences `settled`/`moved`, so it can never accumulate.
  const [driftT, setDriftT] = useState(0);
  useEffect(() => {
    if (reducedMotion) return;
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      setDriftT((now - start) / 1000);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [reducedMotion]);

  const positioned = useMemo(() => {
    return settled.map((n) => {
      const override = moved[n.paperRef];
      if (override) return { ...n, ...override };
      if (reducedMotion) return n;
      const { dx, dy } = driftOffset(n.paperRef, driftT);
      return { ...n, x: n.x + dx, y: n.y + dy };
    });
    // `driftT` drives this memo every frame by design — the drift layer.
  }, [settled, moved, driftT, reducedMotion]);

  const posByRef = useMemo(
    () => new Map(positioned.map((n) => [n.paperRef, n])),
    [positioned],
  );

  const svgRef = useRef<SVGSVGElement>(null);
  const [view, setView] = useState<View>({ x: 0, y: 0, k: 1 });
  // Who has the focus/hover right now — drives the neighbourhood highlight.
  // `pointerenter`/`pointerleave` AND `focus`/`blur` both drive it, so
  // keyboard use gets the same neighbourhood highlight a mouse hover does.
  const [focusRef, setFocusRef] = useState<string | null>(null);
  const active = useMemo(() => activeNeighbourhood(focusRef, adjacency), [focusRef, adjacency]);

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

  const zoomAt = useCallback(
    (sx: number, sy: number, deltaY: number) => {
      setView((v) => {
        const k = clamp(v.k * Math.exp(-deltaY * 0.0015), MIN_K, MAX_K);
        // Keep the point under the cursor fixed while zooming.
        const lx = (sx - v.x) / v.k;
        const ly = (sy - v.y) / v.k;
        return { k, x: sx - lx * k, y: sy - ly * k };
      });
    },
    [],
  );

  // A native, non-passive listener: React attaches `onWheel` as passive at
  // the root for scroll performance, which silently ignores this handler's
  // `preventDefault()` — the page scrolls underneath the graph while you
  // zoom it. Only a listener registered with `{ passive: false }` directly
  // on the element actually blocks the scroll.
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const handler = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const sx = ((e.clientX - rect.left) / rect.width) * W;
      const sy = ((e.clientY - rect.top) / rect.height) * H;
      zoomAt(sx, sy, e.deltaY);
    };
    el.addEventListener("wheel", handler, { passive: false });
    return () => el.removeEventListener("wheel", handler);
  }, [zoomAt]);

  const fit = () => {
    setView({ x: 0, y: 0, k: 1 });
    setMoved({});
  };

  if (graph.nodes.length === 0) {
    return (
      <p className="p-6 text-sm text-text-muted">
        No papers yet. Add an arXiv id, DOI, or PDF, and the neighbourhood grows
        from the citation service.
      </p>
    );
  }

  const panning = gesture.current?.kind === "pan";

  return (
    <figure className="m-0 flex flex-col gap-2">
      <div className="relative h-[var(--constellation-h)] w-full overflow-hidden rounded-card bg-bg">
        {/* A calm field, not a boxed chart: a faint vignette instead of a
         * hard edge, so the graph reads as a space rather than a panel. */}
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
          data-agent="constellation"
          onPointerDown={beginPan}
          onPointerMove={onMove}
          onPointerUp={onUp}
          onPointerCancel={onUp}
          onKeyDown={(e) => {
            if (e.key === "Escape") setFocusRef(null);
          }}
        >
          <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
            {graph.edges.map((e) => {
              const a = posByRef.get(e.src);
              const b = posByRef.get(e.dst);
              if (!a || !b) return null;
              const state = edgeState(e.src, e.dst, focusRef);
              return (
                <line
                  key={`${e.src}-${e.dst}-${e.kind}`}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={state === "incident" ? (EDGE[e.kind]?.color ?? "var(--viz-axis)") : "var(--viz-axis)"}
                  strokeWidth={1}
                  opacity={edgeOpacity(state)}
                  className="transition-opacity duration-standard"
                />
              );
            })}
            {positioned.map((n) => {
              const isSel = n.paperRef === selected;
              const inFocusNeighbourhood = active.has(n.paperRef);
              const r = nodeRadius(degrees.get(n.paperRef) ?? 0);
              const showLabel = labelVisible({
                selected: isSel,
                inFocusNeighbourhood,
                radius: r,
                zoomK: view.k,
              });
              const label = showLabel ? nodeLabel(n) : "";
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
                    fill={n.ingested ? "var(--accent)" : "var(--text-muted)"}
                    fillOpacity={n.ingested ? 1 : 0.45}
                    stroke={highlighted ? "var(--accent)" : "none"}
                    strokeWidth={highlighted ? 2 : 0}
                  />
                  {label && (
                    <text
                      y={r + 11}
                      textAnchor="middle"
                      transform={`scale(${1 / view.k})`}
                      // The counter-scale above keeps this text a constant
                      // rendered size regardless of zoom — without it, a
                      // label would grow right along with the graph.
                      className="fill-text-muted text-[0.625rem]"
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
          className="absolute right-2 top-2 flex items-center gap-1 rounded-input border border-border-strong bg-surface px-2 py-1 text-xs font-medium text-text shadow-brutal-sm transition-colors duration-fast hover:bg-accent-soft hover:text-accent"
          aria-label="Reset the view"
        >
          <Maximize2 className="size-3.5" aria-hidden /> Fit
        </button>
      </div>

      <figcaption className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-muted">
        <span className="text-text-muted/80">Drag to pan · scroll to zoom · drag a node to move · hover or focus a paper to light its neighbourhood</span>
        <LegendDot filled label="ingested" />
        <LegendDot filled={false} label="suggested, click to add" />
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
