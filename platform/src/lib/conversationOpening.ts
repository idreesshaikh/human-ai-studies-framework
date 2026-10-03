import type { Turn } from "./types.ts";

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
