import type { ReactNode } from "react";

/* Every empty view teaches: one wry line and the single next action. */
export function EmptyState({
  line,
  action,
}: {
  line: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-card border border-dashed border-border-strong px-6 py-12 text-center">
      <p className="max-w-md text-sm text-text-muted">{line}</p>
      {action}
    </div>
  );
}
