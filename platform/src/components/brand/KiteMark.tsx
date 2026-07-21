/* The brand mark — one shape reading three ways at once, deliberately:
 * a kite (the cross-spar makes it unmistakably the flown toy, not just a
 * diamond), a phoenix (rendered in the app's own ember accent, the fire
 * that already anchors this palette), and a tern (the forked tail is a
 * birder's field-mark for one). Quiet and static everywhere it appears. */
export function KiteMark({
  size = 32,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden className={className}>
      <path d="M19 4 L28 15 L13 28 L4 14 Z" fill="var(--accent)" />
      <path
        d="M19 4 L13 28 M28 15 L4 14"
        stroke="var(--accent-contrast)"
        strokeWidth="0.75"
        strokeLinecap="round"
        opacity="0.55"
      />
      <path
        d="M12 27 L7.5 31.3 M14 27.5 L16.8 31.5"
        stroke="var(--accent)"
        strokeWidth="1.6"
        strokeLinecap="round"
        fill="none"
      />
    </svg>
  );
}
