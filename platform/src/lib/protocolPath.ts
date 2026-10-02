
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

  done: number;
  total: number;

  upNext: string;
}

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

  const slotSteps: PathStep[] = MANDATORY_SLOTS.map((slot) => ({
    id: `slot:${slot}`,
    label: SLOT_LABELS[slot],
    status: draft[slot].length > 0 ? "done" : "todo",
  }));
  const [steps] = withCursor(slotSteps, cursorTaken);
  phases.push({ title: "Filling the protocol", steps });

  const all = slotSteps;
  return {
    phases,
    done: all.filter((s) => s.status === "done").length,
    total: all.length,
    upNext: understanding?.nextQuestion ?? "",
  };
}
