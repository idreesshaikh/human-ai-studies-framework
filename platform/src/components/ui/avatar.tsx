import { cn } from "@/lib/cn";

/* A small identity circle. When an image is supplied (e.g. a Clerk-hosted
 * avatar in hosted mode) it renders that; otherwise it falls back to the
 * first letter of a name or email. */
export function Avatar({
  name,
  src,
  className,
}: {
  name: string;
  src?: string;
  className?: string;
}) {
  const initial = (name.trim()[0] ?? "?").toUpperCase();
  if (src) {
    return (
      <img
        src={src}
        alt=""
        className={cn("size-7 shrink-0 rounded-chip object-cover", className)}
      />
    );
  }
  return (
    <span
      className={cn(
        "inline-flex size-7 shrink-0 items-center justify-center rounded-chip",
        "bg-zone-9 type-legend text-text",
        className,
      )}
      aria-hidden
    >
      {initial}
    </span>
  );
}
