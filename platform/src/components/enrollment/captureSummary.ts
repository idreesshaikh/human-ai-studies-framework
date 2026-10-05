/* Plain-words summary of a participant's external producer states. The data
 * stays as recorded (`producerStates`); this only decides what the roster says.
 * Only what is ON is listed; everything off collapses into one phrase rather
 * than one jargon item per producer. */
import { captureTokenLabel } from "../../lib/uiText.ts";

export function summarizeProducerStates(
  states: Record<string, string>,
): string {
  const external = Object.entries(states).filter(([id]) => id !== "tern");
  if (external.length === 0) return "";
  const on = external.filter(([, state]) => state === "enabled").map(([id]) => captureTokenLabel(id));
  if (on.length === 0) return "External producers off";
  const anyOff = external.length > on.length;
  return `${on.join(", ")} on${anyOff ? "; other external producers off" : ""}`;
}
