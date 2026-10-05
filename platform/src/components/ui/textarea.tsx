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
      "control control-area min-w-0 type-body leading-relaxed",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";
