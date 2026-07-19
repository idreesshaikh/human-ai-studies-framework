import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

/* Button — a physical keycap. Colours, durations, radii, and the hard offset
 * shadow all come from design tokens via Tailwind utilities. `keycap` (from
 * index.css) adds the hover-lift + press-to-bottom-out; ghost stays flat for
 * quiet inline actions. Labels are set as key legends: mono, uppercase,
 * tracked. */
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-input font-display text-xs font-bold uppercase tracking-wider transition-colors duration-fast disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "keycap border-2 border-border-strong bg-accent text-accent-contrast shadow-brutal",
        outline:
          "keycap border-2 border-border-strong bg-surface text-text shadow-brutal",
        ghost:
          "rounded-input text-text hover:bg-accent-soft hover:text-accent",
        subtle:
          "keycap border-2 border-border-strong bg-accent-soft text-accent shadow-brutal",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 px-3",
        icon: "size-9",
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
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
