import { Avatar } from "@/components/ui/avatar";
import type { PresenceViewer } from "@/lib/presence";

/* Who else is in this study right now (FR-PLAT collaboration). Deliberately
 * quiet: a row of small identity circles, no counter shouting at you, and
 * nothing at all when you're the only one here — an empty state would be
 * noise on the common case of working alone. */
export function PresenceChips({
  viewers,
  meSub,
}: {
  viewers: PresenceViewer[];
  meSub?: string;
}) {
  const others = viewers.filter((v) => v.sub !== meSub);
  if (others.length === 0) return null;
  const shown = others.slice(0, 3);
  const overflow = others.length - shown.length;
  const names = others.map((v) => v.displayName).join(", ");

  return (
    <div
      className="flex items-center gap-1"
      data-agent="presence-chips"
      title={`${names} ${others.length === 1 ? "is" : "are"} viewing this study`}
    >
      <span className="sr-only" aria-live="polite">
        {names} {others.length === 1 ? "is" : "are"} viewing this study
      </span>
      {shown.map((v) => (
        <Avatar
          key={v.sub}
          name={v.displayName}
          className="size-6 ring-1 ring-border"
        />
      ))}
      {overflow > 0 && (
        <span className="tabular type-caption text-text-muted">+{overflow}</span>
      )}
    </div>
  );
}
