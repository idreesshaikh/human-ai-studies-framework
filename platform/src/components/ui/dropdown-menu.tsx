import * as React from "react";
import {
  Menu,
  MenuContent,
  MenuItem,
  MenuSeparator,
  MenuTrigger,
} from "@ui-sdk/react/menu";
import { cn } from "@/lib/cn";
import { asChildRender } from "@/components/ui/as-child";

/* Dropdown menu on ui-sdk (top layer, roving focus, typeahead, ARIA). */
export function DropdownMenu({ children }: { children?: React.ReactNode }) {
  return <Menu>{children}</Menu>;
}

export function DropdownMenuTrigger({
  asChild,
  children,
  ...props
}: Omit<React.ComponentProps<"button">, "children"> & { asChild?: boolean; children?: React.ReactNode }) {
  return <MenuTrigger {...props} {...asChildRender(asChild, children)} />;
}

export function DropdownMenuContent({
  className,
  align = "start",
  sideOffset = 6,
  ...props
}: Omit<React.ComponentProps<"div">, "children"> & {
  children?: React.ReactNode;
  align?: "start" | "center" | "end";
  sideOffset?: number;
}) {
  return (
    <MenuContent
      align={align}
      sideOffset={sideOffset}
      collisionPadding={8}
      className={cn("popup-panel min-w-44 p-1", className)}
      {...props}
    />
  );
}

export function DropdownMenuItem({
  className,
  destructive,
  asChild,
  children,
  onSelect,
  ...props
}: Omit<React.ComponentProps<"div">, "children" | "onSelect"> & {
  children?: React.ReactNode;
  destructive?: boolean;
  asChild?: boolean;
  onSelect?: (event: Event) => unknown;
}) {
  return (
    <MenuItem
      destructive={destructive}
      onSelect={onSelect}
      className={cn("popup-item type-label", destructive ? "text-critical" : "text-text", className)}
      {...props}
      {...asChildRender(asChild, children)}
    />
  );
}

export const DropdownMenuLabel = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("type-caption px-2 py-1.5 text-text-muted", className)} {...props} />
);

export const DropdownMenuSeparator = () => <MenuSeparator className="-mx-1 my-1 h-px bg-border" />;
