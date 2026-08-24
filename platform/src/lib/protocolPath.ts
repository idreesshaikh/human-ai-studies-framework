/* The road from "an idea" to "a protocol", as an ordered list.
 *
 * The conversation already walks a fixed order  -  the elicitation facets
 * first (a design shape is withheld until enough of the idea is understood),
 * then the protocol's own core sections. The rail should make that order legible
 * without turning the researcher into a 13-step form. The current facet is
 * therefore shown as a single focus row; progress belongs to the eight
 * core protocol sections that the draft actually records.
 *
 * Two reviewers asked for the same thing in different words: one for the
 * steps in a "more guided fashion... so that all the information needed for
 * the protocol is asked for in a more systematic way", the other for "an
 * overview somewhere (like a chatlist) of what the user needs to provide" so
 * it is "easier to estimate how long the chat will be".
 *
 * This is that list, derived  -  never invented. Every step comes from state
 * the server already computes; nothing here decides what is required.
 */
import { MANDATORY_SLOTS, SLOT_LABELS } from "./types.ts";
import type { ProtocolDraft, Understanding } from "./types.ts";

export type StepStatus = "done" | "current" | "todo";

export interface PathStep {
  id: string;
  label: string;
  status: StepStatus;
}

export interface PathPhase {
  title: string;
  steps: PathStep[];
}

export interface ProtocolPath {
  phases: PathPhase[];
  /** Steps settled, and steps in total, across both phases. */
  done: number;
  total: number;
  /** The question the conversation is steering toward, or "" when the
   *  understanding phase is finished. Server-authored (elicitation's own
   *  `next_question`), never composed here. */
  upNext: string;
}

/** Marks the first unsettled step in a list as the current one. A phase whose
 *  steps are all done has no current step, which is what lets the *next*
 *  phase claim it  -  only one step on the whole path is ever "current". */
function withCursor(steps: PathStep[], claimed: boolean): [PathStep[], boolean] {
  let taken = claimed;
  const out = steps.map((step) => {
    if (step.status === "done" || taken) return step;
    taken = true;
    return { ...step, status: "current" as const };
  });
  return [out, taken];
}

export function buildProtocolPath(
  draft: ProtocolDraft,
  understanding?: Understanding,
): ProtocolPath {
  const phases: PathPhase[] = [];
  let cursorTaken = false;

  /* Phase one: the single facet the assistant is asking about now. Showing
   * every known and unknown facet here made a calm decision path look like a
   * second checklist. The server's first missing label remains the source of
   * truth for the visible focus. */
  if (understanding) {
    const missing = understanding.missingLabels?.[0];
    phases.push({
      title: "Current focus",
      steps: [
        {
          id: "focus",
          label: missing || "Ready to shape the study",
          status: missing ? "current" : "done",
        },
      ],
    });
    cursorTaken = Boolean(missing);
  }

  /* Phase two: the core sections the conversation fills. Deliberately NOT
   * described as the protocol's requirements  -  SlotMeter documents why those
   * are a different list, and the server's compile stays the authority on
   * readiness. These are steps to walk, not a validity claim. */
  const slotSteps: PathStep[] = MANDATORY_SLOTS.map((slot) => ({
    id: `slot:${slot}`,
    label: SLOT_LABELS[slot],
    status: draft[slot].length > 0 ? "done" : "todo",
  }));
  const [steps] = withCursor(slotSteps, cursorTaken);
  phases.push({ title: "Filling the protocol", steps });

  /* The focus row is orientation, not another protocol requirement. Counting
   * it here was the source of the misleading 1/13 meter. */
  const all = slotSteps;
  return {
    phases,
    done: all.filter((s) => s.status === "done").length,
    total: all.length,
    upNext: understanding?.nextQuestion ?? "",
  };
}
