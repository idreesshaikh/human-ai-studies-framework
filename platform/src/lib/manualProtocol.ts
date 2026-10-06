/* Validation for the manual protocol dialog. Pure: returns one entry per
 * problem, in form order, each naming the field id the error summary links to. */
export interface ManualFormValues {
  title: string;
  researchQuestions: string[];
  conditions: string[];
  participantDescription: string;
  plannedParticipants: string;
  taskDescription: string;
  sessionMinutes: string;
  measures: string[];
}

export interface ManualProblem {
  id: string;
  label: string;
  message: string;
}

const inRange = (raw: string, min: number, max: number) => {
  const n = Number(raw);
  return raw.trim() !== "" && Number.isInteger(n) && n >= min && n <= max;
};

export function validateManualProtocol(v: ManualFormValues): ManualProblem[] {
  const out: ManualProblem[] = [];
  const add = (id: string, label: string, message: string) => out.push({ id, label, message });
  const title = v.title.trim();
  if (title.length < 3) add("manual-title", "Study name", "Enter a study name of at least 3 characters.");
  v.researchQuestions.forEach((q, i) => {
    if (q.trim().length < 10) add(`manual-rq-${i}`, `Research question ${i + 1}`, "Write the question in at least 10 characters.");
  });
  v.conditions.forEach((c, i) => {
    if (!c.trim()) add(`manual-condition-${i}`, `Condition ${i + 1}`, "Name this condition.");
  });
  if (v.participantDescription.trim().length < 2) add("manual-participants", "Who takes part", "Describe who takes part.");
  if (!inRange(v.plannedParticipants, 4, 1000)) add("manual-planned", "Planned participants", "Enter a whole number from 4 to 1000.");
  if (!inRange(v.sessionMinutes, 15, 180)) add("manual-minutes", "Session length", "Enter minutes from 15 to 180.");
  if (v.taskDescription.trim().length < 8) add("manual-task", "Task", "Describe the task in at least 8 characters.");
  if (v.measures.length < 1 || v.measures.length > 6) add("manual-outcomes", "Outcomes", "Choose between one and six outcomes.");
  return out;
}
