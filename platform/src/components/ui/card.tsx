import * as React from "react";
import { cn } from "@/lib/cn";

/* Card — a working sheet laid on the record: squared, framed with a hairline
 * rule, lifted just off the paper by its own shadow. A sheet is a real object
 * in this world, so it is never nested inside another sheet; a division within
 * a sheet is a ruled band, not a second sheet.
 *
 * `askew` is the overlay pose — a sheet laid down by hand sits a fraction off
 * square. Use it for sheets that were *placed* on the record (a proposed
 * move, an amendment), never for the base draft, which is squared to the rail.
 * `lift` adds the hover/press response for a sheet that can be picked up. */
export const Card = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & { askew?: boolean; lift?: boolean }
>(({ className, askew, lift, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "sheet rounded-card text-text",
      askew && "sheet-askew",
      lift && "sheet-lift",
      className,
    )}
    {...props}
  />
));
Card.displayName = "Card";

/* The title block: every sheet names itself, and the name sits on a ruled band
 * rather than floating above the content. */
export const CardHeader = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn(
      "flex flex-col gap-1 border-b border-border px-4 py-3",
      className,
    )}
    {...props}
  />
);

export const CardTitle = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("type-subhead", className)} {...props} />
);

export const CardContent = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("p-4", className)} {...props} />
);
