/* Plain titles for the analysis recipes the protocol can name. Keep this in
 * step with analysis/src/analysis/recipes/*.py (each module declares
 * `id="..."`); scripts/verify-conversation-polish.mjs reads those files and
 * fails when an id has no label here. */
export const RECIPE_LABELS: Record<string, string> = {
  "agent-interaction-dynamics": "Agent interaction dynamics",
  "ai-review-behavior": "AI review behavior",
  "code-quality-by-condition": "Code quality by condition",
  correlation: "Correlation",
  "fatigue-by-condition": "Fatigue by condition",
  "meyer-fragmentation": "Work fragmentation",
  "paired-nonparametric": "Paired comparison (non-parametric)",
  "paste-behavior": "Paste behavior",
  "stuck-episodes": "Stuck episodes",
  "task-outcome-by-condition": "Task outcome by condition",
  "tlx-debrief": "Workload debrief (NASA-TLX)",
  "two-group-nonparametric": "Two-group comparison (non-parametric)",
  "two-proportion": "Two-proportion comparison",
  "ziegler-acceptance-rate": "Suggestion acceptance rate",
};

/** A recipe id as a researcher reads it; an unknown id is humanised. */
export function recipeLabel(id: string): string {
  const known = RECIPE_LABELS[id];
  if (known) return known;
  const words = id.replace(/[-_]+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}
