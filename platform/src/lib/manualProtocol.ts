/* Validation for the manual protocol dialog. Pure: returns one entry per
 * problem, in form order, each naming the field id the error summary links to. */
export interface ManualFormValues {
  title: string;
  design: "within-subjects" | "between-subjects";
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
  if (title.length < 3 || title.length > 160) add("manual-title", "Study name", "Enter a study name of 3 to 160 characters.");
  const questions = new Set<string>();
  v.researchQuestions.forEach((q, i) => {
    const text = q.trim();
    if (text.length < 10 || text.length > 500) add(`manual-rq-${i}`, `Research question ${i + 1}`, "Write the question in 10 to 500 characters.");
    else if (questions.has(text.toLowerCase())) add(`manual-rq-${i}`, `Research question ${i + 1}`, "Each research question must be different.");
    questions.add(text.toLowerCase());
  });
  const conditions = new Set<string>();
  v.conditions.forEach((c, i) => {
    const text = c.trim();
    if (!text || text.length > 80) add(`manual-condition-${i}`, `Condition ${i + 1}`, "Name this condition in 80 characters or fewer.");
    else if (conditions.has(text.toLowerCase())) add(`manual-condition-${i}`, `Condition ${i + 1}`, "The two conditions must be different.");
    conditions.add(text.toLowerCase());
  });
  if (v.participantDescription.trim().length < 2 || v.participantDescription.trim().length > 240) add("manual-participants", "Who takes part", "Describe who takes part in 2 to 240 characters.");
  const minParticipants = v.design === "between-subjects" ? 6 : 4;
  if (!inRange(v.plannedParticipants, minParticipants, 1000)) add("manual-planned", "Planned participants", `Enter a whole number from ${minParticipants} to 1000.`);
  if (!inRange(v.sessionMinutes, 15, 180)) add("manual-minutes", "Session length", "Enter minutes from 15 to 180.");
  if (v.taskDescription.trim().length < 8 || v.taskDescription.trim().length > 500) add("manual-task", "Task", "Describe the task in 8 to 500 characters.");
  if (v.measures.length < 1 || v.measures.length > 6) add("manual-outcomes", "Outcomes", "Choose between one and six outcomes.");
  return out;
}
