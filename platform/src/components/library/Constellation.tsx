import { useMemo } from "react";
import { layoutGraph, type PositionedNode } from "@/lib/forceLayout";
import type { PaperGraph } from "@/lib/studyApi";
import { cn } from "@/lib/cn";

/* The citation constellation (FR-LIT-2) — a study's papers grow a graph around
 * themselves: seed → neighbourhood → grow, ResearchRabbit-style on open data.
 * Deterministic force layout (no d3-force, D17), the dataviz series palette for
 * edge kinds, node radius by citation count. Ingested papers anchor the centre;
 * suggestions drift to the rim, one click from joining the study. */

const W = 640;
const H = 440;

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

export function Constellation({
  graph,
  selected,
  onSelect,
}: {
  graph: PaperGraph;
  selected: string | null;
  onSelect: (ref: string) => void;
}) {
  const positioned = useMemo(
    () => layoutGraph(graph.nodes, graph.edges, { width: W, height: H }),
    [graph],
  );
  const posByRef = useMemo(
    () => new Map(positioned.map((n) => [n.paperRef, n])),
    [positioned],
  );

  if (graph.nodes.length === 0) {
    return (
      <p className="p-6 text-sm text-text-muted">
        No papers yet. Add an arXiv id, DOI, or PDF — the neighbourhood grows
        from the citation service.
      </p>
    );
  }

  return (
    <figure className="m-0 flex flex-col gap-2">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full rounded-card bg-bg"
        role="img"
        aria-label="Citation constellation of the study's papers"
        data-agent="constellation"
      >
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
          const label = nodeLabel(n);
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
              onClick={() => onSelect(n.paperRef)}
              onKeyDown={(ev) => ev.key === "Enter" && onSelect(n.paperRef)}
            >
              <circle
                r={r}
                fill={n.ingested ? "var(--accent)" : "var(--surface)"}
                stroke={isSel ? "var(--accent)" : "var(--viz-axis)"}
                strokeWidth={isSel ? 3 : n.ingested ? 0 : 1.5}
                strokeDasharray={n.ingested ? undefined : "2 2"}
                className="transition-all duration-fast"
              />
              {label && (
                <text
                  y={r + 11}
                  textAnchor="middle"
                  className="select-none fill-text-muted text-[0.625rem]"
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
      </svg>

      <figcaption className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-muted">
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
