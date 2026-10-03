import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

const badgeVariants = cva(
  "type-legend inline-flex items-center gap-1.5 rounded-chip border px-2 py-0.5",
  {
    variants: {
      variant: {
        default: "border-transparent bg-zone-9 text-text",
        grounded: "border-border-strong bg-surface text-text",
        unsourced:
          "border-dashed border-unsourced bg-transparent text-unsourced",
        active: "border-accent bg-accent-wash text-accent",

        filtration: "border-accent bg-accent-wash text-accent",
        outline: "border-border text-text-muted",
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
