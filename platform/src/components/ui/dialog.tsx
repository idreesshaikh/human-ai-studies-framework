import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";

let lastFocusOutsideDialog: HTMLElement | null = null;
if (typeof document !== "undefined") {
  document.addEventListener(
    "focusin",
    (e) => {
      const t = e.target;
      if (!(t instanceof HTMLElement)) return;
      if (t.closest('[role="dialog"]')) return;
      lastFocusOutsideDialog = t;
    },
    true,
  );
}

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;

export const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => {
  return (
  <DialogPrimitive.Portal>

    <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-ink/45 data-[state=open]:animate-in data-[state=open]:fade-in" />
    <DialogPrimitive.Content
      ref={ref}

      onCloseAutoFocus={(e) => {
        const back = lastFocusOutsideDialog;
        if (back && back.isConnected) {
          e.preventDefault();
          back.focus({ preventScroll: true });
        }
      }}
      className={cn(
        "fixed left-1/2 top-1/2 z-50 w-[min(30rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2",
        "flex max-h-[calc(100dvh-2rem)] flex-col",
        "rounded-plate border border-border bg-surface-raised p-5 shadow-lifted",
        "duration-entrance data-[state=open]:animate-in data-[state=open]:fade-in data-[state=open]:zoom-in-95",
        className,
      )}
      {...props}
    >

      <div className="-mr-1 min-h-0 flex-1 overflow-y-auto pr-1">{children}</div>
      <DialogPrimitive.Close
        className="absolute right-4 top-4 rounded-control bg-surface-raised text-text-muted transition-colors duration-fast hover:text-text"
        aria-label="Close"
      >
        <X className="size-4" aria-hidden />
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
  );
});
DialogContent.displayName = "DialogContent";

export const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn("type-subhead text-text", className)}
    {...props}
  />
));
DialogTitle.displayName = "DialogTitle";

export const DialogDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn("mt-1 type-body text-text-muted", className)}
    {...props}
  />
));
DialogDescription.displayName = "DialogDescription";
