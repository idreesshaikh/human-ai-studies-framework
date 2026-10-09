/* Plain row labels for a move's `target` in the review table. A target is a
 * dotted protocol path ("participants.design", "session.durationMinutes").
 * Each leaf gets the word a researcher uses for it, never "Participants •
 * Design": the design is not a participants setting. Keys mirror the
 * compiler's slot list (middleware/compiler.py); verify-polish.mjs reads that
 * file and fails if a slot has no entry here. */
export const ROW_LABELS: Record<string, string> = {
  researchQuestions: "Research questions",
  conditions: "Conditions",
  measures: "Measures",
  instruments: "Instruments",
  "instruments.tern": "Editor capture",
  "instruments.metrics": "Static metrics",
  "instruments.agentCapture": "Agent capture",
  "instruments.taskHarness": "Task harness",
  analysisPlan: "Analysis plan",
  statisticalPlan: "Statistical plan",
  ethics: "Ethics posture",
  design: "Design",
  participants: "Participants",
  "design.conditionOrder": "Condition order",
  "participants.design": "Design",
  "participants.planned": "Sample size",
  "participants.sampleSize": "Sample size",
  "participants.counterbalanced": "Counterbalancing",
  "participants.description": "Participants",
  "session.durationMinutes": "Session length",
  "session.taskDescription": "Task",
  "study.title": "Study name",
  "study.ethicsRef": "Ethics reference",
};

function sentenceCase(segment: string): string {
  const spaced = segment.replace(/([a-z0-9])([A-Z])/g, "$1 $2");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1).toLowerCase();
}

export function rowLabel(target: string): string {
  const cleaned = target.replace(/^protocol\./, "").replace(/\[\]$/, "").trim();
  if (!cleaned) return "The protocol";
  const known = ROW_LABELS[cleaned];
  if (known) return known;
  /* A free-text leaf adds nothing beyond its section ("participants.text"). */
  const parts = cleaned.split(".");
  while (parts.length > 1 && /^(description|text|value|name)$/i.test(parts[parts.length - 1])) parts.pop();
  const trimmed = parts.join(".");
  if (ROW_LABELS[trimmed]) return ROW_LABELS[trimmed];
  /* Unknown path: its last segment alone reads better than a chain. */
  return sentenceCase(parts[parts.length - 1]);
}
