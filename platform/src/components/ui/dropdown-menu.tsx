import * as React from "react";
import * as Menu from "@radix-ui/react-dropdown-menu";
import { Check } from "lucide-react";
import { cn } from "@/lib/cn";

/* Dropdown menu built on Radix (keyboard nav, typeahead, ARIA). */
export const DropdownMenu = Menu.Root;
export const DropdownMenuTrigger = Menu.Trigger;

export const DropdownMenuContent = React.forwardRef<
  React.ElementRef<typeof Menu.Content>,
  React.ComponentPropsWithoutRef<typeof Menu.Content>
>(({ className, sideOffset = 6, ...props }, ref) => (
  <Menu.Portal>
    <Menu.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        "z-50 min-w-44 rounded-card border border-border-strong bg-surface-raised p-1 shadow-brutal",
        "duration-fast data-[state=open]:animate-in data-[state=open]:fade-in",
        className,
      )}
      {...props}
    />
  </Menu.Portal>
));
DropdownMenuContent.displayName = "DropdownMenuContent";

export const DropdownMenuItem = React.forwardRef<
  React.ElementRef<typeof Menu.Item>,
  React.ComponentPropsWithoutRef<typeof Menu.Item> & { destructive?: boolean }
>(({ className, destructive, ...props }, ref) => (
  <Menu.Item
    ref={ref}
    className={cn(
      "flex cursor-default select-none items-center gap-2 rounded-input px-2 py-1.5 text-sm outline-none",
      "focus:bg-accent-soft data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
      destructive ? "text-unsourced" : "text-text",
      className,
    )}
    {...props}
  />
));
DropdownMenuItem.displayName = "DropdownMenuItem";

export function DropdownMenuCheckItem({
  checked,
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof Menu.Item> & { checked?: boolean }) {
  return (
    <DropdownMenuItem {...props}>
      <span className="flex size-4 items-center justify-center">
        {checked && <Check className="size-4 text-accent" aria-hidden />}
      </span>
      {children}
    </DropdownMenuItem>
  );
}

export const DropdownMenuLabel = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("px-2 py-1.5 text-xs text-text-muted", className)} {...props} />
);

export const DropdownMenuSeparator = () => (
  <Menu.Separator className="my-1 h-px bg-border" />
);
