import * as React from "react";
import { Check, ChevronDown } from "lucide-react";
import * as Menu from "@radix-ui/react-dropdown-menu";
import {
  DropdownMenu,
  DropdownMenuContent,
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
    const [menuNode, setMenuNode] = React.useState<HTMLDivElement | null>(null);
    const [open, setOpen] = React.useState(false);
    React.useEffect(() => {
      if (!open) return;
      const current = menuNode?.querySelector<HTMLElement>('[role="menuitemradio"][data-state="checked"]')
        ?? menuNode?.querySelector<HTMLElement>('[role="menuitemradio"]');
      current?.focus();
      const frame = requestAnimationFrame(() => current?.scrollIntoView({ block: "nearest" }));
      return () => cancelAnimationFrame(frame);
    }, [open, menuNode]);

    return (
      <DropdownMenu modal={false} open={open} onOpenChange={setOpen}>
        <DropdownMenuTrigger ref={ref} asChild>
          <button
            type="button"
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
        <DropdownMenuContent
          ref={setMenuNode}
          align="start"
          tabIndex={0}
          regionLabel={ariaLabel ? `${ariaLabel} options` : "Selection options"}
          className="w-[var(--radix-dropdown-menu-trigger-width)] min-w-56 max-w-[calc(100vw-2rem)] max-h-[min(20rem,var(--radix-dropdown-menu-content-available-height))] overflow-y-auto"
        >
          <Menu.RadioGroup
            value={value}
            onValueChange={onValueChange}
          >
          {options.map((option) => (
            <Menu.RadioItem
              key={option.value}
              value={option.value}
              className="relative flex cursor-pointer select-none items-start gap-2 rounded-input py-2 pl-8 pr-2 text-text outline-none focus:bg-zone-9"
            >
              <Menu.ItemIndicator className="absolute left-2 top-2.5 flex size-4 items-center justify-center">
                <Check className="size-4" aria-hidden />
              </Menu.ItemIndicator>
              <div className="flex min-w-0 flex-col">
                <span className="type-body">{option.label}</span>
                {option.hint && (
                  <span className="type-caption text-text-muted">{option.hint}</span>
                )}
              </div>
            </Menu.RadioItem>
          ))}
          </Menu.RadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }
);
Select.displayName = "Select";
