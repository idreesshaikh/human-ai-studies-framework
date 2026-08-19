import { cn } from "@/lib/cn";

/* A paper's continuous quality confidence (0..1) — the signal that replaces
 * the binary Tier A/B hierarchy. Rendered the way an atlas renders every
 * quantity: as MAGNITUDE, a bigger mark for a stronger object, read against
 * the same legend the rest of the app uses, with the number printed beside it
 * in the machine face.
 *
 * Size rather than a coloured bar is the point, and rather than the six hatch
 * densities this replaced. A colour-blind reader, a greyscale print, and a
 * researcher glancing at forty citations at once all resolve "how strongly is
 * this grounded?" from the same mark — and unlike a hatch, a size comparison
 * is pre-attentive: you do not have to consult the key to know which of two
 * marks is larger. A source with no score reads honestly as "unrated", never
 * a faked number. */

/** Confidence maps onto the five magnitudes; below 1/5 there is still a mark,
 * because "scored, but weakly" must never render as "unmarked". */
export function magnitude(value: number): 1 | 2 | 3 | 4 | 5 {
  const step = Math.ceil(Math.min(Math.max(value, 0.001), 1) * 5);
  return Math.min(Math.max(step, 1), 5) as 1 | 2 | 3 | 4 | 5;
}

/** The mark itself, at the magnitude a confidence earns. Decorative by
 * default: every caller here already labels the value in text beside it, so
 * a screen reader would otherwise hear the same number twice. */
export function MagnitudeMark({
  value,
  className,
}: {
  value: number;
  className?: string;
}) {
  return (
    <span aria-hidden className={cn("mag", `mag-${magnitude(value)}`, className)} />
  );
}

export function Confidence({
  value,
  className,
}: {
  value?: number;
  className?: string;
}) {
  if (value == null) {
    return (
      <span
        className={cn("type-legend text-text-muted", className)}
        title="No quality score for this source"
      >
        unrated
      </span>
    );
  }
  const pct = Math.round(value * 100);
  return (
    <span
      className={cn("inline-flex items-center gap-1.5", className)}
      role="img"
      aria-label={`Literature confidence ${pct} percent`}
      title={`Literature confidence ${pct}%`}
    >
      {/* A fixed-width box around a variable-width mark: five magnitudes in a
        * column must align on their centres, or a list of citations reads as
        * a ragged edge rather than as a comparable scale. */}
      <span className="flex size-4 items-center justify-center">
        <MagnitudeMark value={value} />
      </span>
      <span className="type-quantity text-text-muted">{pct}%</span>
    </span>
  );
}
