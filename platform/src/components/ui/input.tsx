import * as React from "react";
import { cn } from "@/lib/cn";

/* Text input — a recessed terminal well: ink keyline, mono text, beige field. */
export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "h-9 w-full rounded-input border-2 border-border-strong bg-bg px-3 py-1 font-mono text-sm text-text",
      "placeholder:text-text-muted focus-visible:border-accent",
      "disabled:cursor-not-allowed disabled:opacity-50",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";
