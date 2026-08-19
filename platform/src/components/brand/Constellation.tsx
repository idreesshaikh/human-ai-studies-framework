/* The living literature constellation — the corpus, drawn as the field of
 * objects it already is.
 *
 * It obeys the same notation as the rest of the app rather than inventing a
 * decorative one: a star's SIZE is its magnitude and the tethers are
 * citations, so the eye learns "bigger mark, stronger evidence" here and takes
 * the same reading into the conversation.
 *
 * Nothing in it is the accent. It is atmosphere behind a page whose one action
 * is a button, and a bright blue object drifting beside the headline gave that
 * page two places to look for one thing.
 *
 * Purely decorative to a screen reader (aria-hidden), it sits behind the
 * hero. Positions are a fixed hand-tuned set — deterministic, so it never
 * reflows between renders — and every colour is a token, so it reads right in
 * both renditions. All motion lives in CSS (index.css) and is frozen
 * automatically under prefers-reduced-motion (tokens.css). */

type Node = {
  x: number;
  y: number;
  /** Magnitude 1–5, the same scale the grounding marks use. */
  m: 1 | 2 | 3 | 4 | 5;
  /** The brightest object in the field. Drawn in ink, never in the accent:
   * this is atmosphere, and the accent on any screen belongs to that screen's
   * one action. */
  lead?: true;
  /** Brightens on a slow cycle, as if freshly cited. */
  glow?: 1 | 2 | 3;
};

/** Radius per magnitude, in the 100×60 viewBox's units. */
const R = { 1: 0.34, 2: 0.5, 3: 0.68, 4: 0.9, 5: 1.15 } as const;

// A calm scatter across a 100×60 field, weighted to the edges so the centre
// stays open for the headline. Most of the field is faint; a few objects are
// bright, and one is the lead.
const NODES: Node[] = [
  { x: 6, y: 12, m: 1 },
  { x: 14, y: 30, m: 4, glow: 1 },
  { x: 9, y: 46, m: 2 },
  { x: 22, y: 18, m: 2 },
  { x: 24, y: 44, m: 1 },
  { x: 33, y: 9, m: 3 },
  { x: 30, y: 33, m: 1 },
  { x: 38, y: 50, m: 3, glow: 2 },
  { x: 46, y: 22, m: 2 },
  { x: 52, y: 40, m: 1 },
  { x: 58, y: 11, m: 4 },
  { x: 63, y: 31, m: 2 },
  { x: 68, y: 49, m: 1 },
  { x: 74, y: 19, m: 5, lead: true },
  { x: 79, y: 38, m: 1 },
  { x: 84, y: 13, m: 2 },
  { x: 88, y: 46, m: 3, glow: 3 },
  { x: 93, y: 27, m: 1 },
  { x: 71, y: 6, m: 1 },
  { x: 45, y: 55, m: 2 },
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
            strokeWidth="0.1"
            opacity="0.22"
          />
        ))}
        {NODES.map((n, i) => (
          <circle
            key={`n${i}`}
            cx={n.x}
            cy={n.y}
            r={R[n.m]}
            fill="var(--mark)"
            className={n.glow ? `constellation-glow glow-${n.glow}` : undefined}
            /* The field recedes; only the lead and the cycling few come
             * forward. A flat opacity across every node is what made the
             * old field read as scattered blobs rather than as a sky. */
            opacity={n.lead ? 0.5 : n.glow ? undefined : 0.24}
          />
        ))}
      </g>
    </svg>
  );
}
