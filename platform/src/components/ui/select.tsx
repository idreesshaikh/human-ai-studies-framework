import * as React from "react";
import { Check, ChevronDown } from "lucide-react";
import {
  Select as SelectRoot,
  SelectContent,
  SelectItem,
  SelectItemIndicator,
  SelectTrigger,
  SelectValue,
} from "@ui-sdk/react/select";
import { cn } from "@/lib/cn";

export interface SelectOption {
  value: string;
  label: string;
  hint?: string;
}

interface SelectProps {
  id?: string;
  "aria-label"?: string;
  "aria-describedby"?: string;
  "aria-invalid"?: boolean;
  value?: string;
  onValueChange?: (value: string) => void;
  options: SelectOption[];
  disabled?: boolean;
  placeholder?: string;
  className?: string;
  ref?: React.Ref<HTMLButtonElement>;
}

/* A single-choice select on ui-sdk: a combobox trigger over a listbox, with
 * typeahead, Home/End, and the chosen option placed over the trigger like a
 * native select. The trigger is the shared `.control` (40px, input radius). */
export function Select({
  id,
  "aria-label": ariaLabel,
  "aria-describedby": ariaDescribedBy,
  "aria-invalid": ariaInvalid,
  value,
  onValueChange,
  options,
  disabled,
  placeholder = "Select…",
  className,
  ref,
}: SelectProps) {
  const items = React.useMemo(
    () => options.map(({ value, label }) => ({ value, label })),
    [options],
  );
  return (
    <SelectRoot
      items={items}
      value={value ?? null}
      onValueChange={(next) => {
        if (typeof next === "string") onValueChange?.(next);
      }}
      disabled={disabled}
      placeholder={placeholder}
    >
      <SelectTrigger
        ref={ref}
        id={id}
        aria-label={ariaLabel}
        aria-describedby={ariaDescribedBy}
        aria-invalid={ariaInvalid || undefined}
        className={cn(
          "control select-trigger relative flex min-w-0 items-center justify-between gap-2 type-body text-left",
          className,
        )}
      >
        <SelectValue className="min-w-0 truncate text-text data-placeholder:text-text-muted" />
        <ChevronDown className="select-chevron size-4 shrink-0 text-text-muted" aria-hidden />
      </SelectTrigger>
      <SelectContent
        collisionPadding={8}
        sideOffset={6}
        className="popup-panel popup-list p-1"
      >
        {options.map((option) => (
          <SelectItem
            key={option.value}
            value={option.value}
            label={option.label}
            className="popup-item relative items-start py-2 ps-8 pe-2 text-text"
          >
            <SelectItemIndicator className="absolute start-2 top-2.5 flex size-4 items-center justify-center text-accent">
              <Check className="size-4" aria-hidden />
            </SelectItemIndicator>
            <span className="flex min-w-0 flex-col">
              <span className="type-body">{option.label}</span>
              {option.hint && <span className="type-caption text-text-muted">{option.hint}</span>}
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </SelectRoot>
  );
}
