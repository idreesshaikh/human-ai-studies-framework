import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

/* Badge — a boxy machine tag: ink keyline, mono label, tracked. Semantic fills
 * carry meaning (magenta brand, phosphor green = cited, amber = your-call). */
const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-chip border-2 px-2 py-0.5 font-display text-xs font-semibold tracking-wide",
  {
    variants: {
      variant: {
        default: "border-border-strong bg-accent-soft text-accent",
        grounded: "border-border-strong bg-surface text-grounded",
        unsourced:
          "border-unsourced border-dashed bg-unsourced-soft text-unsourced",
        outline: "border-border-strong text-text-muted",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export const Badge = ({ className, variant, ...props }: BadgeProps) => (
  <span className={cn(badgeVariants({ variant }), className)} {...props} />
);
