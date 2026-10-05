import * as React from "react";
import { cn } from "@/lib/cn";

/* The one checkbox. A native input (keyboard, forms, screen readers for free)
 * restyled in index.css: an empty bordered box when off, an accent fill with a
 * check when on, a dash when indeterminate. The row is the hit area, at least
 * 24px tall. `bordered` frames the row as a card for option lists. */
export interface CheckboxProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: React.ReactNode;
  description?: React.ReactNode;
  indeterminate?: boolean;
  bordered?: boolean;
  rowClassName?: string;
}

export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ label, description, indeterminate, bordered, className, rowClassName, ...props }, ref) => {
    const inner = React.useRef<HTMLInputElement | null>(null);
    const setRef = (node: HTMLInputElement | null) => {
      inner.current = node;
      if (typeof ref === "function") ref(node);
      else if (ref) ref.current = node;
    };
    React.useEffect(() => {
      if (inner.current) inner.current.indeterminate = Boolean(indeterminate);
    }, [indeterminate]);
    return (
      <label className={cn("checkbox-row", bordered && "checkbox-row--card", rowClassName)}>
        <input ref={setRef} type="checkbox" className={cn("checkbox", className)} {...props} />
        <span className="min-w-0">
          <span className="type-body text-text">{label}</span>
          {description && <span className="block type-caption text-text-muted">{description}</span>}
        </span>
      </label>
    );
  },
);
Checkbox.displayName = "Checkbox";
