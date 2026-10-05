import * as React from "react";
import { cn } from "@/lib/cn";

/* Text field: a ruled cell in the record, set in the reading voice, because
 * what a researcher types here is language rather than measurement. A field
 * that genuinely holds a measured value passes `quantity`, which switches it
 * to the tabular machine face and right-aligns it so values line up down a
 * column.
 *
 * `unit` prints the unit in its own cell against the field's right edge, the
 * way the record prints SEC or M against a time or a filtration. */
export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  quantity?: boolean;
  unit?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, quantity, unit, ...props }, ref) => {
    const field = (
      <input
        ref={ref}
        className={cn(
          unit ? "control-bare focus-ring-owned" : "control min-w-0",
          quantity ? "type-quantity text-right" : "type-body",
          className,
        )}
        {...props}
      />
    );

    if (!unit) return field;

    return (
      <div className="control control-group">
        {field}
        <span className="control-suffix type-caption">
          {unit}
        </span>
      </div>
    );
  },
);
Input.displayName = "Input";
