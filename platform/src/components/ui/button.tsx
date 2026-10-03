import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

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

        danger:
          "plate-lift border border-critical bg-surface text-critical shadow-mark hover:bg-critical hover:text-paper",

        filtration: "plate-lift control-primary border shadow-mark",
        struck: "plate-lift control-ink border shadow-mark",
      },
      size: {

        default: "h-11",
        sm: "h-11 px-3 sm:h-9",
        icon: "size-11 px-0",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {

  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}

        aria-disabled={props.disabled || undefined}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
