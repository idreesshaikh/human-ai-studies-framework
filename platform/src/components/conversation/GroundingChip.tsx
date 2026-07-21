import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { TierBadge } from "./TierBadge";
import type { Grounding } from "@/lib/types";

/* A citation chip: tier badge + the paper title. Hover (or click/focus for
 * keyboard and touch) reveals title, year, venue, and why it's cited. */
export function GroundingChip({ g }: { g: Grounding }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-block">
      <button
        type="button"
        className="cursor-help min-h-9"
        aria-expanded={open}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((v) => !v)}
      >
        <Badge variant="grounded">
          <TierBadge tier={g.tier} />
          <span className="max-w-40 truncate">{g.title}</span>
        </Badge>
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute left-0 top-full z-10 mt-1 block w-72 max-w-[calc(100vw-2rem)] rounded-input border border-border-strong bg-surface-raised p-3 text-xs shadow-brutal"
        >
          <span className="block font-medium text-text">
            {g.title}
            {g.year ? ` (${g.year})` : ""}
          </span>
          {g.venue && (
            <span className="block text-text-muted">{g.venue}</span>
          )}
          <span className="mt-1 block text-text">{g.why}</span>
          <span className="mt-1 block font-mono text-text-muted">{g.ref}</span>
        </span>
      )}
    </span>
  );
}
