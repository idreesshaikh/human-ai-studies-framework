/* The blink comparator's plate arithmetic.
 *
 * A comparator alternates two versions of one document in identical
 * coordinates so that anything unchanged sits perfectly still and only what
 * moved appears to move. That promise rests entirely on how the two plates are
 * built, which is why the arithmetic lives here as a pure function rather than
 * inside the component: it is the part that can be wrong in a way a screenshot
 * cannot show, and `scripts/verify-comparator.mjs` exercises it.
 *
 * Two rules the instrument cannot work without:
 *
 * 1. The `+` / `-` marker is STRIPPED. A unified diff needs it because both
 *    versions share one column; a comparator does not. Kept, it made every
 *    changed line one character wider than its counterpart, so the whole plate
 *    shifted on each blink and *everything* appeared to move.
 * 2. A first compile has no earlier version. Every line is an addition, so the
 *    "before" plate is empty and there is nothing to alternate against;
 *    blinking there flipped the panel to blank and back, which reads as a
 *    broken component rather than as "this document did not exist yet". */

export interface DiffLine {
  line: string;
  kind: "add" | "remove" | "context" | "hunk";
}

export interface Plates {
  /** The whole record in reading order: additions at full ink, removals struck
   * and left legible. This is the resting state, and it is a document rather
   * than an animation. */
  record: DiffLine[];
  /** The document without the additions. Empty on a first compile. */
  before: DiffLine[];
  /** The document without the removals. */
  after: DiffLine[];
  /** Nothing existed before this compile, so the instrument has one plate. */
  firstVersion: boolean;
  /** Rows the container must reserve so a shorter plate's turn cannot collapse
   * the layout — which would be the one motion the comparator must never
   * make. */
  rows: number;
}

function strip(d: DiffLine): DiffLine {
  return d.kind === "add" || d.kind === "remove"
    ? { ...d, line: d.line.slice(1) }
    : d;
}

export function buildPlates(lines: DiffLine[]): Plates {
  const record = lines.map(strip);
  const before = lines.filter((d) => d.kind !== "add").map(strip);
  const after = lines.filter((d) => d.kind !== "remove").map(strip);
  return {
    record,
    before,
    after,
    firstVersion: before.length === 0,
    rows: Math.max(record.length, before.length, after.length),
  };
}

/** Whether an earlier version of the document exists to compare against. A
 * diff of pure additions is a first version, and showing the comparator there
 * would print the same document the compiled-protocol block already shows. */
export function hasEarlierVersion(lines: DiffLine[]): boolean {
  return lines.some((d) => d.kind === "remove" || d.kind === "context");
}
