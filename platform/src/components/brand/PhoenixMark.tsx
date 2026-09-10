/* Phoenix constellation mark. Coordinates are normalized to the SVG viewBox. */

/** The figure: wings spread, head up, one long tail. `m` is the magnitude
 * radius, `lead` marks the single accent star. */
const STARS: { x: number; y: number; m: number; lead?: boolean }[] = [
  { x: 16, y: 6.5, m: 1.9 }, // head
  { x: 4.8, y: 11.6, m: 2.1 }, // left wingtip
  { x: 10.6, y: 13.9, m: 1.5 }, // left shoulder
  { x: 16, y: 15.6, m: 3.1, lead: true }, // the heart  -  the one bright star
  { x: 21.4, y: 13.9, m: 1.5 }, // right shoulder
  { x: 27.2, y: 11.6, m: 2.1 }, // right wingtip
  { x: 16, y: 25.2, m: 1.7 }, // tail
];

/** The tethers, as index pairs into STARS. Head to heart, heart down the
 * tail, and one line out along each wing. */
const LINES: [number, number][] = [
  [0, 3],
  [3, 6],
  [1, 2],
  [2, 3],
  [3, 4],
  [4, 5],
];

export function PhoenixMark({
  size = 32,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      aria-hidden
      className={className}
    >
      {/* The tethers sit under the stars, in the same thread tone the
        * literature constellation uses, so the two fields read as one
        * notation rather than as a logo and a chart. */}
      <g
        stroke="var(--thread)"
        strokeWidth="1"
        strokeLinecap="round"
        opacity="0.55"
      >
        {LINES.map(([a, b]) => (
          <line
            key={`${a}-${b}`}
            x1={STARS[a].x}
            y1={STARS[a].y}
            x2={STARS[b].x}
            y2={STARS[b].y}
          />
        ))}
      </g>
      {STARS.map((s, i) => (
        <circle
          key={i}
          cx={s.x}
          cy={s.y}
          r={s.m}
          fill={s.lead ? "var(--accent)" : "var(--ink)"}
        />
      ))}
    </svg>
  );
}
