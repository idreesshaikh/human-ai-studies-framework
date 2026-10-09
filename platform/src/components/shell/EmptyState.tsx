import type { ReactNode } from "react";

/* Explain what will appear here and the action that starts it. */
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
