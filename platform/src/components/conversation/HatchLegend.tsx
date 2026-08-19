import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/cn";

/* The key — what makes the whole field readable.
 *
 * Every provenance signal in this workspace is a mark, not a colour, and
 * there are exactly four of them: magnitude is how strongly a move is
 * grounded, an open ring is a claim logged but not identified in the
 * literature, a struck line is something superseded but never erased, and a
 * doubled mark is two claims on one slot. A record that uses marks owes the
 * reader its key, printed on the same plate rather than hidden in a help
 * panel — so this sits at the foot of the conversation, where the marks it
 * explains are in view.
 *
 * It is decoration only if the marks are decoration. They are not: they are
 * the reason a colour-blind reader and a greyscale print get the same
 * provenance information as everyone else.
 *
 * On a phone the flat key wraps to three rows and takes the bottom tenth of
 * the screen off the thread it is annotating, so there it prints as the marks
 * alone under one "Key" rule and opens on a tap. From `sm:` up there is room
 * for the whole key at once and it is simply always on the plate.
 *
 * (The file keeps its old name so no import in the workspace has to move for
 * a rename; the component is the key to four marks, not to a hatch.) */

/** The three sample magnitudes the key prints: faint, middling, bright. */
const SAMPLES = [1, 3, 5] as const;

function Magnitudes() {
  return (
    <span aria-hidden className="flex items-end gap-1">
      {SAMPLES.map((m) => (
        <span key={m} className="flex size-4 items-center justify-center">
          <span className={cn("mag", `mag-${m}`)} />
        </span>
      ))}
    </span>
  );
}

export function HatchLegend({
  grounded = true,
  unsourced = true,
  conflict = true,
  superseded = true,
}: {
  /* Which marks are actually on screen. A key is a promise that the reader
   * will meet these marks; printed unconditionally it taught "bigger mark,
   * stronger evidence" on a thread where every move was unsourced and no
   * magnitude mark existed anywhere but in the key itself. Each row appears
   * only once its mark does. Defaults are permissive so a caller that has not
   * been taught to measure still gets the full key rather than none of it. */
  grounded?: boolean;
  unsourced?: boolean;
  conflict?: boolean;
  superseded?: boolean;
}) {
  const [open, setOpen] = useState(false);
  if (!grounded && !unsourced && !conflict && !superseded) return null;

  return (
    <div
      data-agent="hatch-legend"
      className="border-t border-border px-4 py-2 sm:px-6"
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls="hatch-legend-key"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 rounded-control text-text-muted transition-colors duration-fast hover:text-text sm:hidden"
      >
        <span className="type-legend">Key</span>
        {/* The marks alone, as the closed state's whole content; once the
          * key below is open they would just be the same swatches twice. */}
        <span aria-hidden className={cn("items-center gap-2", open ? "hidden" : "flex")}>
          {grounded && <Magnitudes />}
          {unsourced && <span className="mark-unsourced" />}
          {conflict && <span className="mark-conflict" />}
        </span>
        <ChevronDown
          aria-hidden
          className={cn(
            "ml-auto size-4 transition-transform duration-standard",
            open && "rotate-180",
          )}
        />
      </button>

      <div
        id="hatch-legend-key"
        className={cn(
          "flex-wrap items-center gap-x-5 gap-y-2 pt-2 sm:flex sm:pt-0",
          open ? "flex" : "hidden",
        )}
      >
        <span className="type-legend hidden text-text-muted sm:inline">Key</span>

        {grounded && (
          <span className="flex items-center gap-1.5">
            <Magnitudes />
            <span className="type-caption text-text-muted">
              bigger mark, stronger evidence
            </span>
          </span>
        )}

        {unsourced && (
          <span className="flex items-center gap-1.5">
            <span aria-hidden className="mark-unsourced" />
            <span className="type-caption text-text-muted">unsourced: your call</span>
          </span>
        )}

        {conflict && (
          <span className="flex items-center gap-1.5">
            <span aria-hidden className="mark-conflict" />
            <span className="type-caption text-text-muted">conflict</span>
          </span>
        )}

        {superseded && (
          <span className="flex items-center gap-1.5">
            <span aria-hidden className="superseded type-caption">
              superseded
            </span>
            <span className="type-caption text-text-muted">struck, never erased</span>
          </span>
        )}
      </div>
    </div>
  );
}
