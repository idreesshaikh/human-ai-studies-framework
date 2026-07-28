import { useId } from "react";

/* The brand mark: wings swept up, rising out of the flame it burns back
 * from — drawn with deliberately few, large shapes, since it also has to
 * read cleanly at favicon size. `public/favicon.svg` carries the same
 * geometry, hardcoded to hex because a browser tab can't read CSS custom
 * properties — the two are edited together. Ink ground, paper bird, one
 * signal-accent flame, so it inverts correctly per theme. */
export function PhoenixMark({
  size = 32,
  className,
}: {
  size?: number;
  className?: string;
}) {
  const wingId = useId();
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden className={className}>
      <circle cx="16" cy="16" r="16" fill="var(--ink)" />

      {/* The flame first, so the bird sits in front of it. */}
      <path
        d="M16 18.5c2.4 2.6 3.4 5.1 3 7.6-.6 2.4-1.6 3.9-3 4.5-1.4-.6-2.4-2.1-3-4.5-.4-2.5.6-5 3-7.6z"
        fill="var(--accent)"
      />

      <g fill="var(--bg)">
        {/* One wing, swept up and outward; mirrored so the bird is
         * symmetric by construction rather than by eye. useId() keeps the
         * mirrored wing's id unique per instance — two marks on one page
         * (header + hero) would otherwise collide on a duplicate id. */}
        <path
          id={wingId}
          d="M15 15.3C11.6 11.2 7.9 7.9 3.9 5.4c.6 5.3 2.9 9.9 6.9 13.8l4.2-2.2z"
        />
        <use href={`#${wingId}`} transform="translate(32 0) scale(-1 1)" />
        {/* Head, breast and the long tail it tapers into. */}
        <path d="M16 6.4c1.6 0 2.8 1.2 2.8 2.7 0 1-.5 1.8-1.2 2.3l.7 6.9L16 24.6l-2.3-6.3.7-6.9c-.7-.5-1.2-1.3-1.2-2.3 0-1.5 1.2-2.7 2.8-2.7z" />
        {/* Beak. */}
        <path d="M18.5 8.2l2.8 1-2.8 1z" />
      </g>
    </svg>
  );
}
