import * as React from "react";
import { ChevronDown } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
}

export const Select = React.forwardRef<HTMLButtonElement, SelectProps>(
  (
    {
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
    },
    ref
  ) => {
    const selected = options.find((opt) => opt.value === value);

    return (
      <DropdownMenu>
        <DropdownMenuTrigger ref={ref} asChild>
          <button
            id={id}
            aria-label={ariaLabel}
            aria-describedby={ariaDescribedBy}
            aria-invalid={ariaInvalid}
            className={cn(
              "control relative flex min-w-0 items-center justify-between gap-2 type-body text-left",
              className
            )}
            disabled={disabled}
          >
            <span className={cn("min-w-0 truncate", !selected ? "text-text-muted" : "text-text")}>
              {selected?.label ?? placeholder}
            </span>
            <ChevronDown className="size-4 shrink-0 text-text-muted" aria-hidden />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-full min-w-56">
          {options.map((option) => (
            <DropdownMenuCheckItem
              key={option.value}
              checked={value === option.value}
              onSelect={() => onValueChange?.(option.value)}
              className="cursor-pointer"
            >
              <div className="flex flex-col">
                <span className="type-body">{option.label}</span>
                {option.hint && (
                  <span className="type-caption text-text-muted">{option.hint}</span>
                )}
              </div>
            </DropdownMenuCheckItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }
);
Select.displayName = "Select";
