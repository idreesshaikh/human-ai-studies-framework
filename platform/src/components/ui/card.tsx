import * as React from "react";
import { cn } from "@/lib/cn";

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

export const CardContent = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("p-4", className)} {...props} />
);
