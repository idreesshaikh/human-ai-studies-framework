import * as React from "react";
import { cn } from "@/lib/cn";

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
          "h-9 w-full border border-control-edge bg-surface px-3 py-1 text-text",
          "rounded-input placeholder:text-text-muted",

          "transition-colors duration-fast hover:border-text-muted",

          "disabled:cursor-not-allowed disabled:border-border disabled:bg-well disabled:text-text-muted",
          quantity ? "type-quantity text-right" : "type-body",
          unit && "border-r-0",
          className,
        )}
        {...props}
      />
    );

    if (!unit) return field;

    return (
      <div className="flex w-full items-stretch">
        {field}
        <span className="type-legend flex items-center rounded-r-input border border-control-edge bg-zone-9 px-2 text-text-muted">
          {unit}
        </span>
      </div>
    );
  },
);
Input.displayName = "Input";
