import { useEffect, useRef, useState } from "react";
import { ArrowRight, ArrowLeft, X } from "lucide-react";
import { Button } from "@/components/ui/button";

/* A focused, first-study walkthrough. It doesn't just describe the workspace  -
 * it drives it: advancing switches the active tab (via onTab), so each step is
 * read against the surface it's about. Deliberately in-house (no tour library):
 * full keyboard + reduced-motion control, and nothing new to pull in. Shown
 * once (localStorage), and re-openable from the "?" in the workspace. */

export type TourTab =
  | "conversation"
  | "library"
  | "data"
  | "planning"
  | "enrollment";

interface Step {
  tab: TourTab;
  title: string;
  body: string;
}

const STEPS: Step[] = [
  {
    tab: "conversation",
    title: "Configure the study",
    body: "Describe a coding task and the AI comparison. The assistant turns that brief into a protocol TERN can run, while the map keeps only what you accept.",
  },
  {
    tab: "library",
    title: "Keep evidence close",
    body: "Evidence is where you inspect the papers behind a choice. The design surface stays focused on the next decision instead of repeating the whole literature record.",
  },
  {
    tab: "data",
    title: "Run only a valid plan",
    body: "Review the compiled protocol before collection. If a required slot or instrument is invalid, the draft names the problem and keeps Apply disabled.",
  },
  {
    tab: "enrollment",
    title: "Then recruit",
    body: "Once the protocol is valid, create participant links from Run. Data and analysis follow the same protocol record.",
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

  /* Focus has to move INTO the dialog when it opens.
   *
   * This is what makes the rest of the component work at all. The key handler
   * below hangs off this div, and React delivers keydown by bubbling from
   * whatever is focused  -  with focus left on `body`, nothing bubbled through
   * here, so Escape did not close the tour and the arrow keys did not step it.
   * Every keyboard affordance this dialog claims to have was inert.
   *
   * It is also what `aria-modal="true"` promises and did not deliver: with
   * focus outside, Tab walked the app chrome *behind* the scrim (the first
   * stop was the "Phoenix, home" link), so a keyboard or screen-reader user
   * met an obscured page instead of the walkthrough  -  on the very first
   * screen a new researcher sees.
   *
   * The panel takes focus rather than the "Next" button, so a screen reader
   * reads the dialog from its own top instead of starting at the last
   * control; and the element that was focused before is restored on close,
   * so dismissing the tour returns the researcher where they were. */
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    panel.current?.focus();
    return () => previous?.focus?.();
  }, []);

  /* Tab stays inside while it is open. Without this the trap is only
   * advisory: `aria-modal` tells assistive tech to ignore the background, but
   * it does not stop the Tab key from reaching it. */
  const trapTab = (e: React.KeyboardEvent) => {
    if (e.key !== "Tab") return;
    const focusable = panel.current?.querySelectorAll<HTMLElement>(
      'button:not([disabled]),a[href],input:not([disabled]),[tabindex]:not([tabindex="-1"])',
    );
    if (!focusable || focusable.length === 0) return;
    const first = focusable[0];
    const lastEl = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      lastEl.focus();
    } else if (!e.shiftKey && document.activeElement === lastEl) {
      e.preventDefault();
      first.focus();
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-ink/45 p-4 sm:items-center"
      role="dialog"
      aria-modal="true"
      aria-label="Getting started"
      onKeyDown={(e) => {
        if (e.key === "Escape") onClose();
        if (e.key === "ArrowRight" && !last) go(i + 1);
        if (e.key === "ArrowLeft" && i > 0) go(i - 1);
        trapTab(e);
      }}
    >
      {/* `tabIndex={-1}`: focusable by script, never a stop in the Tab order
        * itself. No outline suppression is needed and none is written  -  a
        * programmatic `.focus()` does not match `:focus-visible` (verified in
        * the browser), so the global focus ring in index.css correctly stays
        * off for this hand-off and still fires for every real control inside
        * when the researcher tabs to it. */}
      <div
        ref={panel}
        tabIndex={-1}
        className="w-full max-w-md rounded-card border border-border-strong bg-surface-raised p-5 shadow-lifted"
      >
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
            className="rounded-control -m-2 p-2 text-text-muted transition-colors duration-fast hover:bg-zone-9 hover:text-text"
          >
            <X className="size-4" aria-hidden />
          </button>
        </div>

        <h2 className="type-subhead mt-4 text-text">{step.title}</h2>
        <p className="mt-2 type-body leading-relaxed text-text-muted">{step.body}</p>

        <div className="mt-5 flex items-center justify-between">
          <span className="type-caption text-text-muted">
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

export function markTourSeen() {
  localStorage.setItem(TOUR_KEY, "1");
}
