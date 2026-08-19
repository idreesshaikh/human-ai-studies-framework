import * as React from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/cn";

/* A native <select>, restyled to match the rest of the design system —
 * the OS's own dropdown arrow and default sans font read as an unstyled
 * escape from the instrument aesthetic everywhere else (Input, Button).
 * `appearance-none` strips the native chrome; a single lucide chevron
 * replaces it, positioned over the same input field anatomy. The underlying element stays a real <select> —
 * still opens the OS's native picker and is fully keyboard/screen-reader
 * operable, just dressed to match. */
export const Select = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(({ className, children, ...props }, ref) => (
  <div className="relative">
    <select
      ref={ref}
      className={cn(
        "h-10 w-full appearance-none rounded-input border border-border bg-surface-raised px-3 py-2 pr-8 type-body text-text shadow-mark transition-colors duration-fast",
        "focus-visible:border-accent",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      {children}
    </select>
    <ChevronDown
      aria-hidden
      className="pointer-events-none absolute right-2.5 top-1/2 size-4 -translate-y-1/2 text-text-muted"
    />
  </div>
));
Select.displayName = "Select";
