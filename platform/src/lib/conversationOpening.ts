import type { Turn } from "./types.ts";

/* The prompt the thread opens with, before the researcher has typed anything.
 *
 * This is the whole of what remains of the old client-side design stub. That
 * stub answered from a keyword script whenever the server was unreachable  -
 * an impersonation of the conversation rather than the conversation, and
 * indistinguishable from it on screen. The opening line is different in kind:
 * it asks a question and claims nothing. */
export function openingTurn(opening = ""): Turn {
  const text = opening.trim()
    ? `I have your study brief: “${opening.trim()}” I’ll turn it into a runnable developer study. What coding task will participants complete?`
    : "Describe the coding task, the AI comparison, and the outcome you want to capture. I’ll help configure a runnable developer study, and you can leave non-critical choices open.";
  return {
    turnId: "opening",
    role: "platform",
    author: "Platform",
    text,
    moves: [],
    recommendations: [],
  };
}
