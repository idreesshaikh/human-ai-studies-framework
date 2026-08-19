import { AlertTriangle, CloudOff, Info } from "lucide-react";
import { cn } from "@/lib/cn";

/* Notice — the one way this app tells the researcher something went wrong,
 * something is degraded, or something is worth knowing.
 *
 * It exists because there were four ways. A failed load rendered as a
 * full-width slab of mid-tone fill on one page, as bare red-ish caption text
 * on another, and as an untinted paragraph on a third, so the same event
 * carried a different weight depending on which screen the researcher
 * happened to be on. A researcher cannot learn what a signal means if it
 * looks different every time it fires.
 *
 * The form is the log's own: a flagged entry printed on the plate, its kind
 * carried by the icon and by the weight of its own frame. Not a filled block
 * (a fill competes with the one thing on a screen that is allowed to be
 * filled, the primary action, and a mid-tone fill behind body text is how a
 * message ends up under its contrast floor), and not a thick coloured edge
 * down one side, which is the most recognisable tell of a generated
 * interface and says nothing the icon does not already say.
 *
 * Three kinds, and they are honestly different events:
 *   problem  something failed and the researcher's work did not happen
 *   offline  the platform is degraded but their work is intact
 *   note     something worth knowing; nothing is wrong */
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
