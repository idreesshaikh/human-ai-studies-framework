import { useCallback, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Badge } from "@/components/ui/badge";
import { Confidence, ConfidenceValue, GroundingMark } from "./Confidence";
import type { Grounding } from "@/lib/types";
import { publicPaperReference } from "@/lib/paperReference";

export function GroundingChip({ g }: { g: Grounding }) {
  const [open, setOpen] = useState(false);
  const cardId = useId();
  const anchor = useRef<HTMLSpanElement>(null);
  const card = useRef<HTMLDivElement>(null);
  const [placement, setPlacement] = useState({ left: 0, top: 0 });
  const citation = publicPaperReference(g.ref);

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

    window.addEventListener("scroll", place, true);
    window.addEventListener("resize", place);
    return () => {
      window.removeEventListener("scroll", place, true);
      window.removeEventListener("resize", place);
    };
  }, [open, place]);

  return (

    <span
      ref={anchor}
      className="relative inline-block max-w-full"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onKeyDown={(e) => {

        if (e.key === "Escape" && open) {
          e.stopPropagation();
          setOpen(false);
        }
      }}
    >
      <button
        type="button"
        className="cursor-help min-h-9 max-w-full"
        aria-label={`Grounded citation: ${g.title}${g.confidence != null ? `, confidence ${g.confidence.toFixed(2)}` : ""}`}
        aria-expanded={open}
        aria-describedby={open ? cardId : undefined}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((v) => !v)}
      >

        <Badge
          variant="grounded"
          className="type-caption max-w-full gap-1.5 normal-case tracking-normal"
        >
          {g.confidence != null && (
            <span className="flex shrink-0 items-center gap-1 self-start">
              <GroundingMark value={g.confidence} />
              <ConfidenceValue value={g.confidence} />
            </span>
          )}
          <span className="type-legend shrink-0 text-grounded">grounded</span>

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
            {citation && (
              <span className="type-quantity identifier mt-1 block break-all text-text-muted">
                {citation}
              </span>
            )}
          </div>,
          document.body,
        )}
    </span>
  );
}
