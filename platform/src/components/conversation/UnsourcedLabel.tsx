/* Marks a design move that carries no citation.
 *
 * Unsourced means "your call", not "wrong", so it is drawn as the same open
 * ring the key explains and the draft rail uses for an unfilled slot, not as
 * a warning. It reads as a mark with a label rather than as a bordered pill
 * of tracked caps: the pill put a dashed box around six shouted words on
 * every unsourced card in the thread, which is a lot of chrome to say one
 * quiet thing.
 *
 * A grounded move carries a magnitude mark in the same position, so the two
 * states are read in one place and compared by form. */
export function UnsourcedLabel() {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span aria-hidden className="mark-unsourced" />
      <span className="type-caption text-unsourced">unsourced: your call</span>
    </span>
  );
}
