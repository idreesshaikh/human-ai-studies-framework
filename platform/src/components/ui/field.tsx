import * as React from "react";
import { CircleAlert } from "lucide-react";
import { cn } from "@/lib/cn";
import { Label } from "@/components/ui/label";

/* The single field layout: label (control size), 6px to the control, then a
 * slot for hint (muted caption) and error (critical caption with an icon, so
 * colour is never the only signal). Wires id, aria-describedby and
 * aria-invalid onto its one child control. */
export function Field({
  label,
  id,
  hint,
  error,
  required,
  action,
  className,
  children,
}: {
  label: React.ReactNode;
  id?: string;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  required?: boolean;
  /** Quiet control on the label row, e.g. Remove. */
  action?: React.ReactNode;
  className?: string;
  children: React.ReactElement<Record<string, unknown>>;
}) {
  const auto = React.useId();
  const fieldId = id ?? auto;
  const hintId = hint ? `${fieldId}-hint` : undefined;
  const errorId = error ? `${fieldId}-error` : undefined;
  const describedBy = [children.props["aria-describedby"], hintId, errorId].filter(Boolean).join(" ") || undefined;
  return (
    <div className={cn("field", className)}>
      <div className="flex min-h-6 items-end justify-between gap-2">
        <Label htmlFor={fieldId}>
          {label}
          {required && <span className="sr-only"> (required)</span>}
        </Label>
        {action}
      </div>
      {React.cloneElement(children, {
        id: fieldId,
        "aria-describedby": describedBy,
        "aria-invalid": error ? true : undefined,
        ...(children.props.stepper && typeof label === "string" ? { stepperLabel: label } : {}),
      })}
      <div className="field-slot" aria-live="polite">
        {hint && (
          <p id={hintId} className="type-caption text-text-muted">
            {hint}
          </p>
        )}
        {error && (
          <p id={errorId} className="flex items-start gap-1 type-caption text-critical">
            <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
            <span>{error}</span>
          </p>
        )}
      </div>
    </div>
  );
}
