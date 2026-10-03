import type { CSSProperties } from "react";
import { cn } from "@/lib/cn";

/* Display a source score as a number and a mark in a fixed frame; missing scores are unrated. */

/** The four plain-word bands. The mark is never the only carrier: the words
 * ship beside the score wherever there is room for them. */
export function groundingLabel(value: number): string {
  const step = Math.ceil(Math.min(Math.max(value, 0.001), 1) * 4);
  return (
    ["weak support", "some support", "well grounded", "strongly grounded"][
      Math.min(Math.max(step, 1), 4) - 1
    ] ?? "unsourced"
  );
}

/** The mark: a dot sized by the score, inside the constant reference frame.
 * Decorative  -  the score prints beside it, and `Confidence` carries the
 * accessible name, so a screen reader would otherwise hear the value twice.
 *
 * The diameter arrives as a RATIO, not a length: the raw px live in
 * index.css, where every other mark's dimensions live. */
export function GroundingMark({
  value,
  className,
}: {
  value: number;
  className?: string;
}) {
  const scale = Math.min(Math.max(value, 0), 1);
  return (
    <span
      aria-hidden
      className={cn("mark-framed", className)}
      style={{ "--mark-scale": scale } as CSSProperties}
    />
  );
}

/** The score as it is printed everywhere: two decimals, tabular figures, in
 * the mark's own ink so it reads as struck onto the plate rather than as body
 * copy. */
export function ConfidenceValue({
  value,
  className,
}: {
  value: number;
  className?: string;
}) {
  return (
    <span aria-hidden className={cn("type-quantity text-mark", className)}>
      {value.toFixed(2)}
    </span>
  );
}

export function Confidence({
  value,
  words = true,
  className,
}: {
  value?: number;
  /** Print the plain-word band beside the score. Off in tight rows where the
   * words would wrap; the mark and the score still carry the value. */
  words?: boolean;
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
  const printed = value.toFixed(2);
  const band = groundingLabel(value);
  return (
    <span
      className={cn("inline-flex items-center gap-1.5", className)}
      role="img"
      aria-label={`Literature confidence ${printed}, ${band}`}
      title={`Literature confidence ${printed}  -  ${band}`}
    >
      <GroundingMark value={value} />
      {/* Tabular figures: a column of citations must align on the decimal
        * point, or a list reads as a ragged edge rather than as a comparable
        * scale  -  which is the whole reason the mark is framed. */}
      <ConfidenceValue value={value} />
      {words && <span className="type-caption text-text-muted">{band}</span>}
    </span>
  );
}
