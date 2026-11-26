import * as React from "react";
import {
  Dialog as DialogRoot,
  DialogBackdrop,
  DialogClose as DialogCloseBase,
  DialogContent as DialogContentBase,
  DialogDescription as DialogDescriptionBase,
  DialogTitle as DialogTitleBase,
  DialogTrigger as DialogTriggerBase,
} from "@ui-sdk/react/dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";
import { scrollEdges } from "@/lib/scrollEdges";
import { asChildRender } from "@/components/ui/as-child";

/* ui-sdk supplies the top layer, focus trap, Escape, outside press and inert
 * page; content scrolls within the viewport. */
/* The last element focused OUTSIDE any popup. Tracked once, for the whole
 * app, because a dialog opened from state has no trigger to restore focus to,
 * and Safari on macOS does not focus a clicked button, so "the element focused
 * before it opened" is often <body>. A keyboard user who closes a dialog should
 * not restart from tab stop one. */
let lastFocusOutsideDialog: HTMLElement | null = null;
const POPUP = '[role="dialog"], [role="menu"], [role="listbox"]';
if (typeof document !== "undefined") {
  document.addEventListener(
    "pointerdown",
    (event) => {
      if (!(event.target instanceof Element)) return;
      const opener = event.target.closest<HTMLElement>(
        "button, a[href], input, textarea, select, [tabindex]",
      );
      if (opener && !opener.closest(POPUP)) lastFocusOutsideDialog = opener;
    },
    true,
  );
  document.addEventListener(
    "focusin",
    (e) => {
      const t = e.target;
      if (!(t instanceof HTMLElement) || t === document.body || t.closest(POPUP)) return;
      lastFocusOutsideDialog = t;
    },
    true,
  );
}
const returnFocus = () =>
  lastFocusOutsideDialog?.isConnected ? lastFocusOutsideDialog : null;

export function Dialog({
  open,
  defaultOpen,
  onOpenChange,
  children,
}: {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  children?: React.ReactNode;
}) {
  /* Rendered at <body>, not in place: in place, every ancestor of the dialog
   * stays outside the inert page (a scroll area that holds it reads as an
   * unreachable region), clicks bubble through wrapping labels, and a dialog's
   * form would nest inside a page form. */
  return (
    <DialogRoot
      container={typeof document === "undefined" ? undefined : document.body}
      open={open}
      defaultOpen={defaultOpen}
      onOpenChange={onOpenChange ? (next) => onOpenChange(next) : undefined}
    >
      {children}
    </DialogRoot>
  );
}

type TriggerProps = Omit<React.ComponentProps<"button">, "children" | "value"> & {
  asChild?: boolean;
  children?: React.ReactNode;
};

export function DialogTrigger({ asChild, children, ...props }: TriggerProps) {
  return <DialogTriggerBase {...props} {...asChildRender(asChild, children)} />;
}

export function DialogClose({ asChild, children, ...props }: TriggerProps) {
  return <DialogCloseBase {...props} {...asChildRender(asChild, children)} />;
}

const CloseIcon = ({ className }: { className?: string }) => (
  <DialogCloseBase
    aria-label="Close"
    className={cn(
      "flex size-8 shrink-0 items-center justify-center rounded-control text-text-muted transition-colors duration-fast hover:bg-zone-9 hover:text-text",
      className,
    )}
  >
    <X className="size-4" aria-hidden />
  </DialogCloseBase>
);

/* Structured dialog: DialogHeader (title, one-line description, close), ONE
 * scrolling DialogBody, and a sticky DialogFooter (secondary left of primary).
 * The whole is capped to the viewport (dvh) so the footer is always visible,
 * and becomes a full-height sheet on phones (`.dialog` in index.css). A dialog
 * with no DialogBody keeps the single scrolling plate (palette, confirmations);
 * `variant="drawer"` docks that plate to the left edge (mobile navigation). */
export function DialogContent({
  className,
  children,
  scrollable = true,
  wide,
  variant,
  ...props
}: Omit<React.ComponentProps<"div">, "children"> & {
  children?: React.ReactNode;
  scrollable?: boolean;
  /** Structured dialogs only: the wide (40rem) plate. */
  wide?: boolean;
  variant?: "drawer";
}) {
  const structured = React.Children.toArray(children).some(
    (child) => React.isValidElement(child) && child.type === DialogBody,
  );
  return (
    <>
      <DialogBackdrop className="dialog-scrim" />
      <DialogContentBase
        finalFocus={returnFocus}
        className={cn(
          structured
            ? cn("dialog", wide && "dialog--wide")
            : cn("dialog-plate", variant === "drawer" && "dialog-plate--drawer"),
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
            <CloseIcon className="absolute right-3 top-3 bg-surface-raised" />
          </>
        )}
      </DialogContentBase>
    </>
  );
}

export const DialogHeader = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("dialog-header", className)} {...props}>
    <div className="flex min-w-0 flex-col gap-1">{children}</div>
    <CloseIcon className="-mr-2 -mt-1" />
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
      tabIndex={0}
      role="region"
      aria-label="Dialog content"
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

export function DialogTitle({ className, ...props }: Omit<React.ComponentProps<"h2">, "children"> & { children?: React.ReactNode }) {
  return <DialogTitleBase className={cn("type-subhead text-text", className)} {...props} />;
}

export function DialogDescription({ className, ...props }: Omit<React.ComponentProps<"p">, "children"> & { children?: React.ReactNode }) {
  return <DialogDescriptionBase className={cn("type-body text-text-muted", className)} {...props} />;
}
