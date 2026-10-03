import type { ReactNode } from "react";
import { surfaceClasses, type Measure } from "@/lib/layout";
import { cn } from "@/lib/cn";

export function Surface({
  measure,
  label,
  className,
  bodyClassName,
  children,
}: {
  measure: Measure;
  label: string;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}) {
  const c = surfaceClasses(measure);
  return (
    <div className={cn(c.root, className)}>
      <div
        className={cn(c.body, bodyClassName)}
        tabIndex={0}
        role="region"
        aria-label={label}
      >
        <div className={c.column}>{children}</div>
      </div>
    </div>
  );
}
