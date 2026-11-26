import { useMemo, useRef } from "react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@ui-sdk/react/tooltip";
import { Badge } from "@/components/ui/badge";
import { Confidence } from "./Confidence";
import type { Grounding } from "@/lib/types";
import { publicPaperReference } from "@/lib/paperReference";

/* A citation chip: the paper title (quality shown as a confidence meter in the
 * card). Hover, focus or a press (touch) reveals title, year, venue, confidence,
 * and why it's cited. ui-sdk's tooltip keeps the card hoverable and dismissible
 * with Escape (WCAG 2.2 SC 1.4.13) and renders it in the top layer, so the
 * conversation's scroller cannot clip it. */
export function GroundingChip({ g }: { g: Grounding }) {
  const trigger = useRef<HTMLButtonElement>(null);
  const citation = publicPaperReference(g.ref);
  /* Placed clear of the whole move card, not just the chip: the card's own
   * Accept / Reject row sits right under its citations, and a card opened
   * beside the chip used to cover it. Horizontally it follows the chip;
   * vertically the move card. Read on every position check, so it follows the
   * thread as it scrolls. */
  const anchor = useMemo(
    () => ({
      getBoundingClientRect: () => {
        const chip = trigger.current;
        if (!chip) return new DOMRect();
        const box = chip.getBoundingClientRect();
        const frame = (chip.closest("[data-move-id]") ?? chip).getBoundingClientRect();
        return new DOMRect(box.left, frame.top, box.width, frame.height);
      },
    }),
    [],
  );

  return (
    <Tooltip toggleable delay={120} type="description">
      <TooltipTrigger
        ref={trigger}
        className="cursor-help min-h-9 max-w-full"
        aria-label={`Cited paper: ${g.title}`}
      >
        {/* The chip names the paper and nothing more. Its score is a corpus
          * quality prior (recency, citations, venue; every seed paper gets the
          * same 0.85), not how well the paper supports this card, and printed
          * beside "grounded" on the card it read as exactly that. The score
          * stays in the hover card under its real name. */}
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
          {/* Two lines of title, not one clamped line: a citation cut to
              "MORE CODE, LESS UNDERSTANDING…" identifies nothing, and two of
              them read as the same source. The flex chain above this now has
              a definite width to wrap into (see StudyHome's tab body). */}
          <span className="min-w-0 whitespace-normal text-left">
            {g.title}
            {(g.year || g.venue) && (
              <span className="text-text-muted">{` · ${[g.year, g.venue].filter(Boolean).join(", ")}`}</span>
            )}
          </span>
        </Badge>
      </TooltipTrigger>
      <TooltipContent
        anchor={anchor}
        side="top"
        align="start"
        sideOffset={8}
        collisionPadding={8}
        className="citation-tooltip popup-panel block w-72 rounded-input border-border-strong p-3"
      >
        <span className="type-label block text-text">
          {g.title}
          {g.year ? ` (${g.year})` : ""}
        </span>
        {g.venue && (
          <span className="type-caption block text-text-muted">{g.venue}</span>
        )}
        <span className="mt-1.5 flex items-center gap-2">
          <span className="type-legend text-text-muted">Source quality</span>
          <Confidence value={g.confidence} words={false} />
        </span>
        <span className="type-caption block text-text-muted">
          From recency, citations and venue. It does not measure how well
          this paper supports the card.
        </span>
        {g.why && (
          <span className="mt-2 block">
            <span className="type-legend block text-text-muted">Paper focus</span>
            <span className="type-body mt-1 line-clamp-4 block text-text [overflow-wrap:anywhere]">
              {g.why}
            </span>
          </span>
        )}
        {citation && (
          <span className="type-quantity identifier mt-1 block break-all text-text-muted">
            {citation}
          </span>
        )}
      </TooltipContent>
    </Tooltip>
  );
}
