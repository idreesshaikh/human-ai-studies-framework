import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";
import { scrollEdges } from "@/lib/scrollEdges";

/* Radix supplies focus trapping and Escape handling; content scrolls within the viewport. */
/* The last element focused OUTSIDE any dialog. Tracked once, for the whole
 * app, because a dialog opened from state has no trigger for Radix to restore
 * focus to and a keyboard user who closes one should not restart from tab stop
 * one. Listening on `focusin` catches the value while it is still true; reading
 * `document.activeElement` inside the dialog's own mount effect does not,
 * because focus has already moved in by then. */
let lastFocusOutsideDialog: HTMLElement | null = null;
if (typeof document !== "undefined") {
  // Safari/macOS need not focus a clicked button. Remember the stable opener
  // before a transient menu replaces it, for state-driven dialogs too.
  document.addEventListener(
    "pointerdown",
    (event) => {
      if (!(event.target instanceof Element)) return;
      const opener = event.target.closest<HTMLElement>(
        "button, a[href], input, textarea, select, [tabindex]",
      );
      if (opener && !opener.closest('[role="dialog"], [role="menu"]')) {
        lastFocusOutsideDialog = opener;
      }
    },
    true,
  );
  document.addEventListener(
    "focusin",
    (e) => {
      const t = e.target;
      if (!(t instanceof HTMLElement)) return;
      if (
        t === document.body ||
        t.hasAttribute("data-radix-focus-guard") ||
        t.closest('[role="dialog"], [role="menu"]')
      )
        return;
      lastFocusOutsideDialog = t;
    },
    true,
  );
}

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;

/* Structured dialog: DialogHeader (title, one-line description, close), ONE
 * scrolling DialogBody, and a sticky DialogFooter (secondary left of primary).
 * The whole is capped to the viewport (dvh) so the footer is always visible,
 * and becomes a full-height sheet on phones (`.dialog` in index.css). A dialog
 * with no DialogBody keeps the legacy single scrolling plate (palette,
 * confirmations). */
export const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
    scrollable?: boolean;
    /** Structured dialogs only: the wide (40rem) plate. */
    wide?: boolean;
  }
>(({ className, children, scrollable = true, wide, ...props }, ref) => {
  const structured = React.Children.toArray(children).some(
    (child) => React.isValidElement(child) && child.type === DialogBody,
  );
  return (
    <DialogPrimitive.Portal>
      {/* The scrim is the record's own ink, not a generic black: over the
       * atlas's cool ground a neutral black reads as a grey wash. */}
      <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-scrim data-[state=open]:animate-in data-[state=open]:fade-in" />
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
          structured
            ? cn("dialog", wide && "dialog--wide")
            : cn(
                "fixed left-1/2 top-1/2 z-50 w-[min(30rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2",
                "flex max-h-[calc(100dvh-2rem)] flex-col",
                "rounded-plate border border-border bg-surface-raised p-5 shadow-lifted",
              ),
          "duration-entrance data-[state=open]:animate-in data-[state=open]:fade-in data-[state=open]:zoom-in-95",
          className,
        )}
        {...props}
      >
        {structured ? (
          children
        ) : (
          <>
            {/* When it scrolls, `-mr-1 pr-1` keeps the scrollbar off the text
             * without shifting the content; a body that does not scroll must not
             * carry it (it would widen the dialog past its container). */}
            <div
              className={cn(
                "min-h-0 flex-1",
                scrollable ? "-mr-1 overflow-y-auto pr-1" : "flex flex-col overflow-hidden",
              )}
            >
              {children}
            </div>
            <DialogPrimitive.Close
              className="absolute right-4 top-4 rounded-control bg-surface-raised text-text-muted transition-colors duration-fast hover:text-text"
              aria-label="Close"
            >
              <X className="size-4" aria-hidden />
            </DialogPrimitive.Close>
          </>
        )}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
});
DialogContent.displayName = "DialogContent";

export const DialogHeader = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("dialog-header", className)} {...props}>
    <div className="flex min-w-0 flex-col gap-1">{children}</div>
    <DialogPrimitive.Close
      className="-mr-2 -mt-1 flex size-8 shrink-0 items-center justify-center rounded-control text-text-muted transition-colors duration-fast hover:bg-zone-9 hover:text-text"
      aria-label="Close"
    >
      <X className="size-4" aria-hidden />
    </DialogPrimitive.Close>
  </div>
);

export const DialogBody = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => {
  const ref = React.useRef<HTMLDivElement>(null);
  const [edges, setEdges] = React.useState({ above: false, below: false });
  const measure = React.useCallback(() => {
    const el = ref.current;
    if (!el) return;
    const next = scrollEdges(el.scrollTop, el.clientHeight, el.scrollHeight);
    setEdges((cur) => (cur.above === next.above && cur.below === next.below ? cur : next));
  }, []);
  React.useEffect(() => {
    measure();
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    Array.from(el.children).forEach((child) => observer.observe(child));
    return () => observer.disconnect();
  }, [measure]);
  return (
    <div
      ref={ref}
      onScroll={measure}
      data-more-above={edges.above ? "" : undefined}
      data-more-below={edges.below ? "" : undefined}
      tabIndex={edges.above || edges.below ? 0 : undefined}
      role={edges.above || edges.below ? "region" : undefined}
      aria-label={edges.above || edges.below ? "Dialog content" : undefined}
      className={cn("dialog-body", className)}
      {...props}
    >
      {children}
    </div>
  );
};

export const DialogFooter = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("dialog-footer", className)} {...props} />
);

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
    className={cn("type-body text-text-muted", className)}
    {...props}
  />
));
DialogDescription.displayName = "DialogDescription";
