import * as React from "react";
import { cn } from "@/lib/cn";

/* Long-form text field for research briefs and notes. Unlike a single-line
 * input, it gives the researcher room to paste a complete brief without
 * turning the first step into a cramped prompt. */
export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "min-h-28 w-full resize-y border border-control-edge bg-surface px-3 py-2 text-text",
      "rounded-input placeholder:text-text-muted",
      "type-body leading-relaxed transition-colors duration-fast hover:border-text-muted",
      "disabled:cursor-not-allowed disabled:border-border disabled:bg-well disabled:text-text-muted",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";
