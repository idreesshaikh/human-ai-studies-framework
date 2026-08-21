import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

/* Badge — a key printed in the margin of the record. Rounded, hairline-ruled,
 * set in the small tracked voice an atlas labels its keys in.
 *
 * Provenance is carried by the mark's FORM, never by its colour alone, so each
 * variant pairs its tone with a form a greyscale print and a colour-blind
 * reader both resolve:
 *   grounded  — a solid, ruled key, carrying the citation's own framed
 *               magnitude mark and score: cited into the corpus
 *   unsourced — the open ring's dashed outline: your call, not an error
 *   active    — the one accent mark, for the single thing in play
 * `default` and `outline` are unmarked keys carrying no provenance claim. */
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
        /* Legacy alias — `filtration` was the old world's name for the one
         * mark that says "this is in play". */
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
