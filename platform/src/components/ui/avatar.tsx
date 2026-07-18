import { cn } from "@/lib/cn";

/* A small identity circle showing the first letter of a name or email.
 * No image loading — identities here are subs/emails, not photos. */
export function Avatar({ name, className }: { name: string; className?: string }) {
  const initial = (name.trim()[0] ?? "?").toUpperCase();
  return (
    <span
      className={cn(
        "inline-flex size-7 shrink-0 items-center justify-center rounded-chip",
        "bg-accent-soft text-xs font-medium text-accent",
        className,
      )}
      aria-hidden
    >
      {initial}
    </span>
  );
}
