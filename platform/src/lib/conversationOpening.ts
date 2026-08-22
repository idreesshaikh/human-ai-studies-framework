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
    ? `I have your starting idea: “${opening.trim()}” Let’s make it testable. Who should take part, and what will they do?`
    : "Let’s turn your idea into a study. Who should take part, and what will they do?";
  return {
    turnId: "opening",
    role: "platform",
    author: "Platform",
    text,
    moves: [],
    recommendations: [],
  };
}
