import type { ReactNode } from "react";
import { surfaceClasses, type Measure } from "@/lib/layout";
import { cn } from "@/lib/cn";

/* Every screen is a Surface, owning exactly four things: one measure, one
 * gutter, one rhythm, one scroller. Three nested elements because each does
 * a different job  -  a root that clips, a body that scrolls, and a measured
 * centred column. One class on one div can't express that; putting clip,
 * scroll, and measure on the same element is exactly how panels ended up
 * with a column that never centred, or two scrollbars fighting each other.
 *
 * The body is a real keyboard target (`tabIndex`, `role="region"`,
 * `aria-label`)  -  hiding the scrollbar (index.css) must not also remove the
 * only way to reach it without a pointer. */
export function Surface({
  measure,
  label,
  className,
  bodyClassName,
  children,
  "data-agent": dataAgent,
}: {
  measure: Measure;
  label: string;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
  "data-agent"?: string;
}) {
  const c = surfaceClasses(measure);
  return (
    <div className={cn(c.root, className)} data-agent={dataAgent}>
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
