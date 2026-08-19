import * as React from "react";
import { cn } from "@/lib/cn";

/* Form label. */
export const Label = React.forwardRef<
  HTMLLabelElement,
  React.LabelHTMLAttributes<HTMLLabelElement>
>(({ className, ...props }, ref) => (
  <label
    ref={ref}
    className={cn("type-body font-medium text-text", className)}
    {...props}
  />
));
Label.displayName = "Label";
