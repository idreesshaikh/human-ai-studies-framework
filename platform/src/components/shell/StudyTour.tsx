import { useState } from "react";
import { ArrowRight, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

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
    tab: "planning",
    title: "Run only a valid plan",
    body: "Plan shows the participant journey, tasks, timing, and capture scope. Review and apply the compiled protocol from Setup before collecting data; unresolved issues keep Apply disabled.",
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

  /* The shared Dialog supplies what this component used to hand-roll: focus
   * moves in on open, Tab stays inside, Escape closes, and focus returns to
   * the opener. Only the arrow keys are the tour's own. */
  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogContent
        onKeyDown={(e) => {
          if (e.key === "ArrowRight" && !last) go(i + 1);
          if (e.key === "ArrowLeft" && i > 0) go(i - 1);
        }}
      >
        <DialogHeader>
          <DialogTitle>Getting started</DialogTitle>
          <DialogDescription>
            Step {i + 1} of {STEPS.length}
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          <h3 className="type-label font-semibold text-text">{step.title}</h3>
          <p className="mt-2 type-body text-text-muted">{step.body}</p>
        </DialogBody>
        <DialogFooter>
          <Button type="button" variant="outline" size="sm" onClick={onClose}>
            Skip
          </Button>
          {i > 0 && (
            <Button type="button" variant="outline" size="sm" onClick={() => go(i - 1)}>
              <ArrowLeft aria-hidden /> Back
            </Button>
          )}
          {last ? (
            <Button size="sm" onClick={onClose}>
              Start
            </Button>
          ) : (
            <Button size="sm" onClick={() => go(i + 1)}>
              Next <ArrowRight aria-hidden />
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const TOUR_KEY = "phoenix.studyTourSeen";

export function markTourSeen() {
  localStorage.setItem(TOUR_KEY, "1");
}
