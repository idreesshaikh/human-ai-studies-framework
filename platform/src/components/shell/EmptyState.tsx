import type { ReactNode } from "react";

/* Every empty view teaches: what will appear here, and the one action that
 * gets it there.
 *
 * The frame is dashed, which is this world's mark for "logged, nothing
 * identified yet"  -  the same notation an unsourced claim and an unfilled
 * protocol slot wear. A solid plate around an empty region reads as a thing
 * that exists and happens to be blank; a dashed one reads as a space waiting
 * to be filled, which is what it is. Quiet by construction: no icon, no
 * illustration, no exclamation. */
export function EmptyState({
  line,
  action,
  className,
}: {
  /* A node, not a string: an empty state often has to name the exact field or
   * metric that is missing, and an identifier is set in the measurement voice
   * rather than in prose. */
  line: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={[
        "flex flex-col items-center gap-4 rounded-plate border border-dashed border-border-strong px-6 py-10 text-center",
        className ?? "",
      ]
        .join(" ")
        .trim()}
    >
      <p className="type-body max-w-md text-text-muted">{line}</p>
      {action}
    </div>
  );
}
