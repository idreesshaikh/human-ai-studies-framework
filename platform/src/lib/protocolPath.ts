/* The road from "an idea" to "a protocol", as an ordered list.
 *
 * The conversation already walks a fixed order — the elicitation facets
 * first (a design shape is withheld until enough of the idea is understood),
 * then the protocol's own sections. Both halves existed; neither was ever
 * shown as a sequence. A researcher saw a row of eight dots filling up and a
 * line naming what was missing, which answers "how far along am I" but not
 * "what is still going to be asked of me, and how much of it is there".
 *
 * Two reviewers asked for the same thing in different words: one for the
 * steps in a "more guided fashion... so that all the information needed for
 * the protocol is asked for in a more systematic way", the other for "an
 * overview somewhere (like a chatlist) of what the user needs to provide" so
 * it is "easier to estimate how long the chat will be".
 *
 * This is that list, derived — never invented. Every step comes from state
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
 *  phase claim it — only one step on the whole path is ever "current". */
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

  /* Phase one: the facets a design shape actually follows from. Driven by the
   * server's own facet map so the order and the naming match the questions
   * the conversation asks — a second list here would drift from it. Absent
   * before the first turn comes back, in which case the path is just the
   * protocol sections. */
  if (understanding) {
    const facetSteps: PathStep[] = Object.entries(understanding.facets).map(
      ([id, known]) => ({
        id: `facet:${id}`,
        /* Named by the server's own facet labels. An earlier version paired
         * `missingLabels` to facets by position, which silently mislabelled
         * every step the researcher had already completed — the labels only
         * travel for the MISSING facets, so the indices stop lining up the
         * moment one is known. */
        label: understanding.facetLabels?.[id] ?? id,
        status: known ? "done" : "todo",
      }),
    );
    const [steps, taken] = withCursor(facetSteps, cursorTaken);
    cursorTaken = taken;
    phases.push({ title: "Understanding your idea", steps });
  }

  /* Phase two: the eight sections the conversation fills. Deliberately NOT
   * described as the protocol's requirements — SlotMeter documents why those
   * are a different list, and the server's compile stays the authority on
   * readiness. These are steps to walk, not a validity claim. */
  const slotSteps: PathStep[] = MANDATORY_SLOTS.map((slot) => ({
    id: `slot:${slot}`,
    label: SLOT_LABELS[slot],
    status: draft[slot].length > 0 ? "done" : "todo",
  }));
  const [steps] = withCursor(slotSteps, cursorTaken);
  phases.push({ title: "Filling the protocol", steps });

  const all = phases.flatMap((p) => p.steps);
  return {
    phases,
    done: all.filter((s) => s.status === "done").length,
    total: all.length,
    upNext: understanding?.nextQuestion ?? "",
  };
}
