import { useId, useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/cn";

/* Keeps its content mounted so a form survives a close, animates the height
 * with a grid row, and takes the content out of the tab order while closed. */
export function Disclosure({
  summary,
  children,
  defaultOpen = false,
  open: controlledOpen,
  onOpenChange,
  align = "start",
  className,
  buttonClassName,
  contentClassName,
}: {
  summary: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  align?: "start" | "center";
  className?: string;
  buttonClassName?: string;
  contentClassName?: string;
}) {
  const [uncontrolledOpen, setUncontrolledOpen] = useState(defaultOpen);
  const open = controlledOpen ?? uncontrolledOpen;
  const setOpen = (next: boolean) => {
    if (controlledOpen === undefined) setUncontrolledOpen(next);
    onOpenChange?.(next);
  };
  const contentId = useId();
  const centered = align === "center";

  return (
    <div className={className}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={contentId}
        onClick={() => setOpen(!open)}
        className={cn(
          "group flex w-full items-center gap-2 type-caption text-text-muted transition-colors duration-fast hover:text-text",
          centered ? "justify-center text-center" : "justify-between text-left",
          buttonClassName,
        )}
      >
        <span className={cn("min-w-0", !centered && "flex-1")}>{summary}</span>
        <ChevronDown
          aria-hidden
          className={cn(
            "size-4 shrink-0 transition-transform duration-standard ease-out",
            open && "rotate-180",
          )}
        />
      </button>
      <div
        id={contentId}
        data-open={open}
        inert={!open}
        aria-hidden={!open}
        className={cn(
          "grid grid-rows-[0fr] opacity-0 transition-[grid-template-rows,opacity] duration-standard ease-out data-[open=true]:grid-rows-[1fr] data-[open=true]:opacity-100",
          contentClassName,
        )}
      >
        <div className="min-h-0 overflow-hidden">{children}</div>
      </div>
    </div>
  );
}
