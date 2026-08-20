import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";

/* Modal dialog built on Radix (focus trap, ARIA, Escape, scroll lock come
 * from the primitive).
 *
 * The content is capped at the viewport and scrolls INSIDE itself. Without
 * that cap a tall dialog (the finish review, with a compiled protocol and a
 * diff in it) grew past the top and bottom of the window: because it is
 * centred with a -50% translate, the overflow went off BOTH edges, the page
 * behind it was scroll-locked by the primitive, and the clipped content was
 * unreachable by pointer, wheel, or keyboard. The close button sits outside
 * the scrolling region so it never scrolls away from the reader.
 *
 * Radix returns focus to the trigger on close, but only when the dialog was
 * opened BY a trigger it owns. Every dialog in this app is opened from state
 * (a button elsewhere flips `open`), so there is nothing for Radix to return
 * to and focus fell to `<body>`: a keyboard user who closed the finish review
 * restarted from tab stop 1 of 30. `DialogContent` therefore remembers what
 * had focus when it mounted and restores it on unmount. */
/* The last element focused OUTSIDE any dialog. Tracked once, for the whole
 * app, because a dialog opened from state has no trigger for Radix to restore
 * focus to and a keyboard user who closes one should not restart from tab stop
 * one. Listening on `focusin` catches the value while it is still true; reading
 * `document.activeElement` inside the dialog's own mount effect does not,
 * because focus has already moved in by then. */
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
    {/* The scrim is the record's own ink, not a generic black: over the
      * atlas's cool ground a neutral black reads as a grey wash. */}
    <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-ink/45 data-[state=open]:animate-in data-[state=open]:fade-in" />
    <DialogPrimitive.Content
      ref={ref}
      /* Radix returns focus to the trigger it owns; every dialog here is
       * opened from state instead, so there was nothing for it to return to and
       * focus fell to <body>. `lastFocusOutsideDialog` is tracked continuously
       * at the document level, which is the only place that still knows what
       * the researcher was on BEFORE the dialog stole focus. */
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
      {/* `-mr-1 pr-1` keeps the scrollbar off the text without shifting the
        * content when the dialog is short enough not to need one. */}
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
