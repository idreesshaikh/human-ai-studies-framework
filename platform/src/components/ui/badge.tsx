import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

/* Badge. */
const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-chip border px-2 py-0.5 text-xs font-medium",
  {
    variants: {
      variant: {
        default: "border-transparent bg-accent-soft text-accent",
        grounded: "border-transparent bg-surface text-grounded",
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
