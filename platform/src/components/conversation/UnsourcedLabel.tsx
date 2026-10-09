/* An unsourced choice remains usable and identifiable; it is not a validation error. */
export function UnsourcedLabel() {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span aria-hidden className="mark-unsourced" />
      <span className="type-caption text-unsourced">No source: your call</span>
    </span>
  );
}
