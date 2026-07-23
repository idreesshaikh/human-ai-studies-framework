/* The living literature constellation — the platform's own metaphor made into
 * quiet ambient artwork. Faint paper-nodes strung together with the brand's
 * kite-string (--thread); a handful glow "grounded" green, the colour a cited
 * move already wears elsewhere. Purely decorative (aria-hidden), it sits behind
 * the hero. Positions are a fixed hand-tuned set — deterministic, so it never
 * reflows between renders — and every colour is a token, so it reads right in
 * both themes. All motion lives in CSS (index.css) and is frozen automatically
 * under prefers-reduced-motion (tokens.css). */

type Node = { x: number; y: number; r: number; grounded?: 1 | 2 | 3 };

// A calm scatter across a 100×60 field, weighted to the edges so the centre
// stays open for the headline. Three nodes are "grounded" (they glow).
const NODES: Node[] = [
  { x: 6, y: 12, r: 0.7 },
  { x: 14, y: 30, r: 1.1, grounded: 1 },
  { x: 9, y: 46, r: 0.8 },
  { x: 22, y: 18, r: 0.9 },
  { x: 24, y: 44, r: 0.7 },
  { x: 33, y: 9, r: 1 },
  { x: 30, y: 33, r: 0.7 },
  { x: 38, y: 50, r: 0.9, grounded: 2 },
  { x: 46, y: 22, r: 0.8 },
  { x: 52, y: 40, r: 0.7 },
  { x: 58, y: 11, r: 1.1 },
  { x: 63, y: 31, r: 0.8 },
  { x: 68, y: 49, r: 0.7 },
  { x: 74, y: 19, r: 0.9, grounded: 3 },
  { x: 79, y: 38, r: 0.7 },
  { x: 84, y: 13, r: 0.8 },
  { x: 88, y: 46, r: 1 },
  { x: 93, y: 27, r: 0.7 },
  { x: 71, y: 6, r: 0.7 },
  { x: 45, y: 55, r: 0.7 },
];

// Threads between nearby nodes (index pairs), the constellation's "citations".
const EDGES: [number, number][] = [
  [0, 1], [1, 2], [1, 3], [3, 5], [1, 6], [6, 8], [4, 7], [7, 9],
  [8, 10], [9, 11], [11, 13], [10, 11], [13, 15], [13, 14], [14, 16],
  [15, 17], [11, 12], [12, 13], [5, 18], [7, 19], [16, 17], [10, 18],
];

export function Constellation({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 100 60"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      focusable="false"
    >
      <g className="constellation-drift">
        {EDGES.map(([a, b], i) => (
          <line
            key={`e${i}`}
            x1={NODES[a].x}
            y1={NODES[a].y}
            x2={NODES[b].x}
            y2={NODES[b].y}
            stroke="var(--thread)"
            strokeWidth="0.12"
            opacity="0.28"
          />
        ))}
        {NODES.map((n, i) => (
          <circle
            key={`n${i}`}
            cx={n.x}
            cy={n.y}
            r={n.r}
            fill={n.grounded ? "var(--grounded)" : "var(--accent)"}
            className={n.grounded ? `constellation-glow glow-${n.grounded}` : undefined}
            opacity={n.grounded ? undefined : "0.4"}
          />
        ))}
      </g>
    </svg>
  );
}
