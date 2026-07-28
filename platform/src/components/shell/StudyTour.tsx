import { useState } from "react";
import { ArrowRight, ArrowLeft, X } from "lucide-react";
import { Button } from "@/components/ui/button";

/* A focused, first-study walkthrough. It doesn't just describe the workspace —
 * it drives it: advancing switches the active tab (via onTab), so each step is
 * read against the surface it's about. Deliberately in-house (no tour library):
 * full keyboard + reduced-motion control, and nothing new to pull in. Shown
 * once (localStorage), and re-openable from the "?" in the workspace. */

export type TourTab =
  | "conversation"
  | "library"
  | "data"
  | "lifecycle"
  | "enrollment";

interface Step {
  tab: TourTab;
  title: string;
  body: string;
}

const STEPS: Step[] = [
  {
    tab: "conversation",
    title: "Talk your study into existence",
    body: "Start here. Describe a research idea in plain language: the assistant asks the questions a methodologist would and proposes design moves you accept or reject. Type “finish” when you're ready to compile them into a protocol.",
  },
  {
    tab: "conversation",
    title: "Every move is grounded, or honest that it isn't",
    body: "Each proposed move cites real papers from the corpus, with a confidence score. Moves that are genuinely your judgment say so, rather than pretending to be cited.",
  },
  {
    tab: "library",
    title: "Your literature, as a living map",
    body: "The papers behind your study: add any by arXiv id, DOI, or PDF. The assistant's recommendations land here too. Drag the constellation to explore the citation neighbourhood.",
  },
  {
    tab: "data",
    title: "Honest data, and the stats your design calls for",
    body: "Your collected data as plain shapes, never a bare p-value. The prescription panel tells you the exact test, effect size, and correction your design needs, with the reasoning.",
  },
  {
    tab: "lifecycle",
    title: "Move the study forward, one checkpoint at a time",
    body: "Design → ethics → pilot → data collection → analysis. Attest each gate (ethics approval, consent) to advance: the study can't skip a step it hasn't cleared.",
  },
  {
    tab: "enrollment",
    title: "Bring participants in",
    body: "Mint a link for each participant. They paste it once into VS Code (the “TERN: Connect to Study” command) and their editor joins the study.",
  },
];

export function StudyTour({
  onTab,
  onClose,
}: {
  onTab: (tab: TourTab) => void;
  onClose: () => void;
}) {
  const [i, setI] = useState(0);
  const step = STEPS[i];
  const last = i === STEPS.length - 1;

  const go = (next: number) => {
    const clamped = Math.max(0, Math.min(STEPS.length - 1, next));
    setI(clamped);
    onTab(STEPS[clamped].tab);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/30 p-4 sm:items-center"
      role="dialog"
      aria-modal="true"
      aria-label="Getting started"
      onKeyDown={(e) => {
        if (e.key === "Escape") onClose();
        if (e.key === "ArrowRight" && !last) go(i + 1);
        if (e.key === "ArrowLeft" && i > 0) go(i - 1);
      }}
    >
      <div className="w-full max-w-md rounded-card border border-border-strong bg-surface-raised p-5 shadow-brutal-lg">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            {STEPS.map((_, n) => (
              <span
                key={n}
                className={
                  "size-1.5 rounded-chip transition-colors duration-fast " +
                  (n === i ? "bg-accent" : "bg-border")
                }
                aria-hidden
              />
            ))}
          </div>
          <button
            onClick={onClose}
            aria-label="Skip the tour"
            className="text-text-muted hover:text-text"
          >
            <X className="size-4" aria-hidden />
          </button>
        </div>

        <h2 className="type-subhead mt-4 text-text">{step.title}</h2>
        <p className="mt-2 text-sm leading-relaxed text-text-muted">{step.body}</p>

        <div className="mt-5 flex items-center justify-between">
          <span className="text-xs text-text-muted">
            Step {i + 1} of {STEPS.length}
          </span>
          <div className="flex items-center gap-2">
            {i > 0 && (
              <Button variant="ghost" size="sm" onClick={() => go(i - 1)}>
                <ArrowLeft aria-hidden /> Back
              </Button>
            )}
            {last ? (
              <Button size="sm" onClick={onClose} data-agent="tour-done">
                Start
              </Button>
            ) : (
              <Button size="sm" onClick={() => go(i + 1)} data-agent="tour-next">
                Next <ArrowRight aria-hidden />
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

const TOUR_KEY = "phoenix.studyTourSeen";

/** Whether the first-study tour has been dismissed before (persisted so it
 * shows once, then only on explicit request). */
export function tourSeen(): boolean {
  return localStorage.getItem(TOUR_KEY) === "1";
}

export function markTourSeen() {
  localStorage.setItem(TOUR_KEY, "1");
}
