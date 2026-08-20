import { useCallback, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Badge } from "@/components/ui/badge";
import { Confidence } from "./Confidence";
import { GradeMark, magnitude } from "./GradeMark";
import type { Grounding } from "@/lib/types";

/* A citation chip: the paper title (quality shown as a confidence meter in the
 * hover card). Hover (or click/focus for keyboard and touch) reveals title,
 * year, venue, confidence, and why it's cited. */
export function GroundingChip({ g }: { g: Grounding }) {
  const [open, setOpen] = useState(false);
  const cardId = useId();
  const anchor = useRef<HTMLSpanElement>(null);
  const card = useRef<HTMLDivElement>(null);
  const [placement, setPlacement] = useState({ left: 0, top: 0 });

  /* The card renders into <body> and is placed from the chip's own box. As an
   * absolutely-positioned sibling it was clipped by the conversation's
   * scroller — a citation opened near the foot of the thread was sheared
   * mid-ref against the scroller's edge — and position:fixed does not escape
   * it either, because the move card itself establishes a containing block.
   * Out in the body it can also flip above the chip when there is no room
   * below. Hover still works across the gap: React routes mouseenter/leave
   * through its own tree, so the portal counts as inside this wrapper. */
  const place = useCallback(() => {
    const a = anchor.current;
    const c = card.current;
    if (!a || !c) return;
    const box = a.getBoundingClientRect();
    const size = c.getBoundingClientRect();
    const gutter = 8;
    const below = box.bottom + gutter;
    const fitsBelow = below + size.height <= window.innerHeight - gutter;
    setPlacement({
      left: Math.max(
        gutter,
        Math.min(box.left, window.innerWidth - size.width - gutter),
      ),
      top: fitsBelow ? below : Math.max(gutter, box.top - size.height - gutter),
    });
  }, []);

  useLayoutEffect(() => {
    if (!open) return;
    place();
    // The thread scrolls under an open card; follow the chip rather than
    // leaving the citation stranded where it was opened.
    window.addEventListener("scroll", place, true);
    window.addEventListener("resize", place);
    return () => {
      window.removeEventListener("scroll", place, true);
      window.removeEventListener("resize", place);
    };
  }, [open, place]);

  return (
    /* Hover state lives on the wrapper, not the button: WCAG 2.2 SC 1.4.13
     * requires the revealed content to be hoverable, and closing on the
     * button's own mouseleave made the gap between chip and card uncrossable,
     * so a pointer user could never reach the full title the chip clamps. */
    <span
      ref={anchor}
      className="relative inline-block max-w-full"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onKeyDown={(e) => {
        // Dismissible without moving the pointer or the focus (same SC).
        if (e.key === "Escape" && open) {
          e.stopPropagation();
          setOpen(false);
        }
      }}
    >
      <button
        type="button"
        className="cursor-help min-h-9 max-w-full"
        aria-expanded={open}
        aria-describedby={open ? cardId : undefined}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((v) => !v)}
      >
        {/* The chip is clean; the citation's own confidence is the small
          * magnitude mark at its left, read against the same key as every
          * other quantity in the app. A wall of citations still reads as a
          * field of magnitudes — the strong support is visible before a
          * single title is read — without marking up the whole chip. */}
        {/* `normal-case` and the caption voice: the Badge's own role is
          * `type-legend`, which uppercases and tracks its label. That is right
          * for a key ("OWNER", "DESIGN") and wrong for a citation, which is
          * somebody's PAPER TITLE: it shipped as
          * "INVESTIGATING AND DESIGNING FOR TRUST IN AI-POWERED CODE
          * GENERATION TOOLS", which is not what the paper is called and is
          * markedly harder to read at two lines. */}
        <Badge
          variant="grounded"
          className="type-caption max-w-full gap-1.5 normal-case tracking-normal"
        >
          {g.confidence != null && (
            /* Four pips, filled based on confidence level (1-4 scale). This replaces
               the continuous magnitude mark with a discrete five-level system for
               clearer visual comparison across citations. */
            <span className="mt-0.5 shrink-0 self-start">
              <GradeMark level={magnitude(g.confidence)} />
            </span>
          )}
          {/* Two lines of title, not one clamped line: a citation cut to
              "MORE CODE, LESS UNDERSTANDING…" identifies nothing, and two of
              them read as the same source. The flex chain above this now has
              a definite width to wrap into (see StudyHome's tab body). */}
          <span className="line-clamp-2 min-w-0 text-left">{g.title}</span>
        </Badge>
      </button>
      {open &&
        createPortal(
          <div
            ref={card}
            id={cardId}
            role="tooltip"
            style={{ left: `${placement.left}px`, top: `${placement.top}px` }}
            className="fixed z-50 block w-72 max-w-[calc(100vw-2rem)] rounded-input border border-border-strong bg-surface-raised p-3 shadow-lifted"
          >
            <span className="type-label block text-text">
              {g.title}
              {g.year ? ` (${g.year})` : ""}
            </span>
            {g.venue && (
              <span className="type-caption block text-text-muted">{g.venue}</span>
            )}
            <span className="mt-1.5 flex items-center gap-2">
              <span className="type-legend text-text-muted">Confidence</span>
              <Confidence value={g.confidence} />
            </span>
            <span className="type-body mt-1 block text-text">{g.why}</span>
            <span className="type-quantity identifier mt-1 block break-all text-text-muted">
              {g.ref}
            </span>
          </div>,
          document.body,
        )}
    </span>
  );
}
