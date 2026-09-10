import { AlertTriangle, CloudOff, Info } from "lucide-react";
import { cn } from "@/lib/cn";

/* Shared notices: failed actions, offline state, and contextual information. */
const KINDS = {
  problem: {
    icon: AlertTriangle,
    rule: "border-critical/40",
    ink: "text-critical",
  },
  offline: {
    icon: CloudOff,
    rule: "border-control-edge",
    ink: "text-text-muted",
  },
  note: {
    icon: Info,
    rule: "border-accent/40",
    ink: "text-text-muted",
  },
} as const;

export function Notice({
  kind = "note",
  children,
  className,
  ...rest
}: {
  kind?: keyof typeof KINDS;
  children: React.ReactNode;
  className?: string;
} & React.HTMLAttributes<HTMLDivElement>) {
  const { icon: Icon, rule, ink } = KINDS[kind];
  return (
    <div
      /* A problem is announced; a note is not. `alert` interrupts a screen
       * reader mid-sentence, which is right for "your work did not happen"
       * and wrong for "here is some context". */
      role={kind === "problem" ? "alert" : undefined}
      className={cn(
        "flex items-start gap-2.5 rounded-plate border border-border bg-surface px-3 py-2.5",
        rule,
        className,
      )}
      {...rest}
    >
      <Icon aria-hidden className={cn("mt-0.5 size-4 shrink-0", ink)} />
      <div className="type-body min-w-0 flex-1 text-text">{children}</div>
    </div>
  );
}
