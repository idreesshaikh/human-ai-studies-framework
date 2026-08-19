import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

/* Button — a control on the plate. Rounded, hairline-framed, and set in the
 * product's own sentence-case voice: mono is reserved for measured
 * quantities, and tracked caps made every control shout its label in a tool
 * whose job is to be quiet enough to think in.
 *
 * The hierarchy is one decision, not a palette. `default` is the accent fill:
 * the next action in its region, and a second one in the same region means one
 * of the two is wrong (the budget is per region, not per viewport: see
 * tokens.css). Everything else is unfilled, an outline or a cleared step or a
 * bare mark, so the eye finds the action without reading a word. `ink` exists
 * for a commit that must not read as the helpful next step, and `danger` for
 * one that removes something.
 *
 * A disabled control drops OUT of its variant rather than fading inside it.
 * A washed-out accent fill still reads as "the blue button", so a primary
 * action waiting on an empty field looked like a broken button rather than
 * an inert one; dropping to the well and muted ink is unmistakable, and it
 * keeps its label legible, which fading below 50% does not. */
const buttonVariants = cva(
  "type-control inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-control px-4 text-center transition-all duration-fast disabled:pointer-events-none disabled:border-border disabled:bg-well disabled:text-text-muted disabled:shadow-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "plate-lift control-primary border shadow-mark",
        outline:
          "plate-lift border border-control-edge bg-surface text-text shadow-mark hover:bg-zone-9",
        ghost:
          "border border-transparent text-text-muted hover:bg-zone-9 hover:text-text",
        subtle:
          "plate-lift border border-border bg-zone-9 text-text shadow-mark hover:border-control-edge",
        ink: "plate-lift control-ink border shadow-mark",
        /* A destructive commit. It stays UNFILLED at rest, because the one
         * fill on a screen means "the helpful next step" and deleting never
         * is; it fills critical only under the pointer, once the researcher
         * has already typed the confirmation. Reached for wherever an action
         * removes something a colleague could be relying on. */
        danger:
          "plate-lift border border-critical bg-surface text-critical shadow-mark hover:bg-critical hover:text-paper",
        /* Legacy aliases — `filtration` and `struck` were the old world's
         * names for "the one next action" and "a committed control". Both
         * resolve into this world's single fill so no call site changes
         * meaning while it is being migrated. */
        /* Legacy aliases kept so no call site changes meaning while it is
         * migrated; both resolve into this world's single fill. */
        filtration: "plate-lift control-primary border shadow-mark",
        struck: "plate-lift control-ink border shadow-mark",
      },
      size: {
        default: "h-10",
        sm: "h-8 px-3",
        icon: "size-10 px-0",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /** Render as the child element (e.g. a router <Link>) instead of a
   * <button>, keeping the button styling. */
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        /* `disabled` alone is announced inconsistently across screen readers
         * on a styled button, and a refused control that only LOOKS refused
         * teaches nothing. Mirroring it to `aria-disabled` costs nothing and
         * makes the state audible as well as visible. */
        aria-disabled={props.disabled || undefined}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
