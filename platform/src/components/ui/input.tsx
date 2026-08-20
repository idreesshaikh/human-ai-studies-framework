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
          "h-9 w-full border border-control-edge bg-surface px-3 py-1 text-text",
          "rounded-input placeholder:text-text-muted",
          /* The global focus ring (index.css) is the whole focus treatment.
           * Turning the border accent as well drew a second blue ring two
           * pixels inside the first, which read as a rendering fault rather
           * than as focus. The border still answers hover, so the field is
           * not inert-looking before it is focused. */
          "transition-colors duration-fast hover:border-text-muted",
          /* Refused the way every other control refuses: the field drops out
           * to the recessed well with muted ink, rather than fading. Fading
           * is the treatment `button.tsx` documents at length as wrong ("a
           * washed-out accent fill still reads as the blue button"), so a
           * disabled field and a disabled button in one form were declining
           * in two different visual languages. */
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
