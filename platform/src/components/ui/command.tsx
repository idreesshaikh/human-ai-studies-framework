import * as React from "react";
import { Command as CommandPrimitive } from "cmdk";
import { Dialog, DialogContent } from "./dialog.tsx";
import { cn } from "@/lib/cn";

/* Command palette built on cmdk (fuzzy match + full keyboard nav). Rendered
 * inside the Radix dialog so focus trapping and Escape come for free. */
export function CommandDialog({
  open,
  onOpenChange,
  label,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="p-0">
        <CommandPrimitive
          label={label}
          className="flex max-h-[24rem] w-full flex-col overflow-hidden rounded-card"
        >
          {children}
        </CommandPrimitive>
      </DialogContent>
    </Dialog>
  );
}

export const CommandInput = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Input>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Input>
>(({ className, ...props }, ref) => (
  <div className="border-b border-border px-3">
    <CommandPrimitive.Input
      ref={ref}
      className={cn(
        "h-11 w-full bg-transparent text-sm text-text outline-none placeholder:text-text-muted",
        className,
      )}
      {...props}
    />
  </div>
));
CommandInput.displayName = "CommandInput";

export const CommandList = CommandPrimitive.List;

export const CommandEmpty = ({
  className,
  ...props
}: React.ComponentPropsWithoutRef<typeof CommandPrimitive.Empty>) => (
  <CommandPrimitive.Empty
    className={cn("p-4 text-center text-sm text-text-muted", className)}
    {...props}
  />
);

export const CommandGroup = CommandPrimitive.Group;

export const CommandItem = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Item>
>(({ className, ...props }, ref) => (
  <CommandPrimitive.Item
    ref={ref}
    className={cn(
      "flex cursor-default select-none items-center gap-2 rounded-input px-3 py-2 text-sm text-text outline-none",
      "data-[selected=true]:bg-accent-soft",
      className,
    )}
    {...props}
  />
));
CommandItem.displayName = "CommandItem";
