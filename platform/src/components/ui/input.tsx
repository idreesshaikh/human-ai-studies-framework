import * as React from "react";
import { Minus, Plus } from "lucide-react";
import { cn } from "@/lib/cn";
import { stepNumber } from "@/lib/fieldStep";

/* Text field. Every field in the app wears `.control` (index.css): one
 * height, border, radius, no shadow, one focus ring. A measured value passes
 * `quantity` (tabular machine face, right-aligned).
 *
 * `unit` and `stepper` turn the field into an input GROUP: the field, its unit
 * (plain muted text) and a quiet -/+ stepper share ONE border and radius. The
 * native number spinners are always hidden; arrow keys still step. */
export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  quantity?: boolean;
  unit?: string;
  /** Number inputs only: integrated -/+ buttons (arrow keys work regardless). */
  stepper?: boolean;
  stepperLabel?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, quantity, unit, stepper, stepperLabel, ...props }, ref) => {
    const inner = React.useRef<HTMLInputElement | null>(null);
    const setRef = (node: HTMLInputElement | null) => {
      inner.current = node;
      if (typeof ref === "function") ref(node);
      else if (ref) ref.current = node;
    };
    const grouped = Boolean(unit || stepper);

    const step = (direction: 1 | -1) => {
      const el = inner.current;
      if (!el) return;
      const num = (v: string | number | undefined) => (v === undefined || v === "" ? undefined : Number(v));
      const next = stepNumber(el.value, direction, {
        min: num(props.min),
        max: num(props.max),
        step: num(props.step) ?? 1,
      });
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
      setter?.call(el, next);
      el.dispatchEvent(new Event("input", { bubbles: true }));
    };

    const field = (
      <input
        ref={setRef}
        className={cn(
          grouped ? "control-bare focus-ring-owned" : "control min-w-0",
          quantity ? "type-quantity text-right" : "type-body",
          className,
        )}
        {...props}
      />
    );
    if (!grouped) return field;

    const label = stepperLabel ?? props["aria-label"] ?? "value";
    return (
      <div className="control control-group">
        {field}
        {unit && <span className="control-suffix type-caption">{unit}</span>}
        {stepper && (
          <>
            <button type="button" className="control-step" aria-label={`Decrease ${label}`} disabled={props.disabled || props.readOnly} onClick={() => step(-1)}>
              <Minus className="size-4" aria-hidden />
            </button>
            <button type="button" className="control-step" aria-label={`Increase ${label}`} disabled={props.disabled || props.readOnly} onClick={() => step(1)}>
              <Plus className="size-4" aria-hidden />
            </button>
          </>
        )}
      </div>
    );
  },
);
Input.displayName = "Input";
