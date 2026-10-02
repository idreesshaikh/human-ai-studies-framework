import type { ReactNode } from "react";

export function EmptyState({
  line,
  action,
  className,
}: {

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
